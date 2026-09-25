"""End-to-end host flow over signed loopback HTTP; never connects to the arm."""
import hashlib
import hmac
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import shutil
import subprocess
from threading import Thread

import pytest

from rocell.application.characterization_http import CharacterizationHTTP
from rocell.application.characterization_request_auth import sign_request
from rocell.application.reviewed_hover_manifest import (
    encode_reviewed_hover_start, ghost_key_manifest, validate_manifest,
)
from rocell.application.reviewed_hover_simulated_host import ReviewedHoverLoopbackHost
from rocell.application.reviewed_hover_live_admission import encode_live_admission
from rocell.application.reviewed_hover_live_host import (
    ReviewedHoverLiveHost, R89_RELEASE_SHA, R90_RELEASE_SHA, R90_APP_SHA,
)
from rocell.application.wizard_diagnostic_export import verify_export


ROOT = Path(__file__).resolve().parents[2]
BOOT = "ab" * 16
KEY = bytes(range(32))


@pytest.fixture(scope="module")
def records(tmp_path_factory):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Native compiler unavailable")
    target = tmp_path_factory.mktemp("reviewed-hover-socket") / "owner.exe"
    result = subprocess.run([compiler, "-std=c++17", "-O2",
        str(ROOT / "firmware/diagnostics/test_reviewed_hover_owner.cpp"),
        "-o", str(target)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    output = subprocess.run([str(target), "success"], capture_output=True,
                            text=True, timeout=10)
    assert output.returncode == 0, output.stderr
    digest = bytes.fromhex(validate_manifest(ghost_key_manifest())["manifest_sha256"])
    return [bytes.fromhex(line)[:26] + digest + bytes.fromhex(line)[58:]
            for line in output.stdout.splitlines()]


class ControllerSimulator:
    def __init__(self, records, fault=None, live=False, release_sha256=R89_RELEASE_SHA,
                 status_delay_polls=0):
        self.records = records
        self.fault = fault
        self.live = live
        self.release_sha256 = release_sha256
        self.leg = 1
        self.sequence = 0
        self.receipts = []
        self.calls = []
        self.status_delay_polls = status_delay_polls
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.respond()

            def do_POST(self):
                self.respond()

            def respond(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                method, path = self.command, self.path
                assert self.headers["X-Rocell-Sequence"] == str(owner.sequence)
                assert self.headers["X-Rocell-Signature"] == sign_request(
                    key=KEY, boot=BOOT, sequence=owner.sequence,
                    method=method, path=path, body=body).hex()
                owner.calls.append((method, path, body))
                suffix = path.rsplit("/", 1)[-1]
                assert path.startswith("/rocell/reviewed-hover/")
                if suffix == "start":
                    expected = (encode_live_admission(ghost_key_manifest(), boot=BOOT,
                        release_sha256=owner.release_sha256,
                        authorize_noncontact_motion=True) if owner.live else
                        encode_reviewed_hover_start(ghost_key_manifest()))
                    assert body == expected
                    response = b"CAPTURING_START"
                elif suffix == "status":
                    if owner.status_delay_polls:
                        owner.status_delay_polls -= 1
                        response = f"CAPTURING_START|{owner.leg}".encode()
                    else:
                        response = f"AWAITING_EXPORT|{owner.leg}".encode()
                elif suffix == "record":
                    response = owner.records[owner.leg - 1].hex().encode()
                elif suffix == "receipt":
                    assert body == (f"{owner.leg}:" + hashlib.sha256(
                        owner.records[owner.leg - 1]).hexdigest()).encode()
                    owner.receipts.append(owner.leg)
                    if owner.fault == ("lost_receipt", owner.leg):
                        self.close_connection = True
                        return
                    owner.leg += 1
                    response = b"COMPLETE" if owner.leg == 17 else f"READY|{owner.leg}".encode()
                elif suffix == "next":
                    assert body == str(owner.leg).encode()
                    response = b"CAPTURING_START"
                else:
                    raise AssertionError(path)
                unsigned = (b"RCCRESPONSE01\0" + bytes.fromhex(BOOT) +
                    owner.sequence.to_bytes(4, "big") + (200).to_bytes(2, "big") +
                    hashlib.sha256(response).digest())
                signature = hmac.digest(KEY, unsigned, "sha256").hex()
                self.send_response(200)
                self.send_header("Content-Length", str(len(response)))
                self.send_header("X-Rocell-Sequence", str(owner.sequence))
                self.send_header("X-Rocell-Signature", signature)
                self.end_headers()
                self.wfile.write(response)
                owner.sequence += 1

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def client(self):
        return CharacterizationHTTP("127.0.0.1", self.server.server_port,
                                    key=KEY, boot=BOOT,
                                    reviewed_hover_live_release_sha256=(
                                        self.release_sha256 if self.live else None))

    def close(self):
        self.server.shutdown(); self.server.server_close()
        self.thread.join(timeout=2)
        assert not self.thread.is_alive()


def test_complete_native_records_over_authenticated_loopback(records, tmp_path):
    simulator = ControllerSimulator(records)
    try:
        host = ReviewedHoverLoopbackHost(simulator.client(),
            manifest=ghost_key_manifest(), boot=BOOT, export_root=tmp_path)
        result = host.run_once()
        assert result["status"] == "REVIEWED_HOVER_SIMULATED_COMPLETE"
        assert simulator.receipts == list(range(1, 17))
        assert all(verify_export(Path(path))["valid"] for path in result["exports"])
        assert not result["motion_authorized"]
        with pytest.raises(ValueError, match="consumed"):
            host.run_once()
    finally:
        simulator.close()


def test_corrupt_record_stops_before_receipt_over_loopback(records, tmp_path):
    altered = records[:]
    bad = bytearray(altered[7]); bad[59] = 2; altered[7] = bytes(bad)
    simulator = ControllerSimulator(altered)
    try:
        host = ReviewedHoverLoopbackHost(simulator.client(),
            manifest=ghost_key_manifest(), boot=BOOT, export_root=tmp_path)
        with pytest.raises(ValueError, match="Simulated campaign stopped; evidence:"):
            host.run_once()
        assert simulator.receipts == list(range(1, 8))
        assert len(list(tmp_path.glob("wizard-*"))) == 8
    finally:
        simulator.close()


def test_lost_receipt_stops_without_next_or_retry_over_loopback(records, tmp_path):
    simulator = ControllerSimulator(records, fault=("lost_receipt", 8))
    try:
        host = ReviewedHoverLoopbackHost(simulator.client(),
            manifest=ghost_key_manifest(), boot=BOOT, export_root=tmp_path)
        with pytest.raises(ValueError, match="Simulated campaign stopped; evidence:"):
            host.run_once()
        assert simulator.receipts == list(range(1, 9))
        assert host.session.stopped
        assert host.session.uncertainty["continuation_may_have_been_authorized"]
        assert simulator.calls[-1][1].endswith("/receipt")
        assert simulator.calls[-1][2].startswith(b"8:")
    finally:
        simulator.close()


def test_loopback_host_rejects_nonloopback_and_used_session(tmp_path):
    remote = CharacterizationHTTP("192.168.0.225", 80, key=KEY, boot=BOOT)
    with pytest.raises(ValueError, match="loopback"):
        ReviewedHoverLoopbackHost(remote, manifest=ghost_key_manifest(),
                                  boot=BOOT, export_root=tmp_path)
    local = CharacterizationHTTP("127.0.0.1", 1, key=KEY, boot=BOOT)
    local.session.request("GET", "/rocell/reviewed-hover/status")
    with pytest.raises(ValueError, match="loopback"):
        ReviewedHoverLoopbackHost(local, manifest=ghost_key_manifest(),
                                  boot=BOOT, export_root=tmp_path)


def test_live_runner_complete_over_loopback_with_durable_claim(records, tmp_path):
    simulator = ControllerSimulator(records, live=True)
    try:
        client = simulator.client()
        host = ReviewedHoverLiveHost(client, boot=BOOT, export_root=tmp_path,
            authorize_noncontact_motion=True)
        result = host.run_once()
        assert result["status"] == "REVIEWED_HOVER_LIVE_COMPLETE"
        assert result["receipts_sent"] == 16
        assert result["hardware_access"] and result["motion_authorized"]
        assert simulator.receipts == list(range(1, 17))
        assert all(row["source_kind"] == "live_controller" for row in result["rows"])
        assert all(verify_export(Path(path))["valid"] for path in result["exports"])
        assert (tmp_path / f"reviewed-hover-live-{BOOT}.json").exists()
        second = ReviewedHoverLiveHost(simulator.client(), boot=BOOT,
            export_root=tmp_path, authorize_noncontact_motion=True)
        before = list(simulator.calls)
        with pytest.raises(ValueError, match="claimed"):
            second.run_once()
        assert simulator.calls == before
    finally:
        simulator.close()


def test_r90_live_runner_binds_new_release_and_app(records, tmp_path):
    simulator = ControllerSimulator(records, live=True, release_sha256=R90_RELEASE_SHA)
    try:
        client = simulator.client()
        host = ReviewedHoverLiveHost(client, boot=BOOT, export_root=tmp_path,
            authorize_noncontact_motion=True, release_sha256=R90_RELEASE_SHA)
        result = host.run_once()
        assert result["status"] == "REVIEWED_HOVER_LIVE_COMPLETE"
        assert simulator.receipts == list(range(1, 17))
        marker = (tmp_path / f"reviewed-hover-live-{BOOT}.json").read_text()
        assert R90_APP_SHA in marker and R90_RELEASE_SHA in marker
    finally:
        simulator.close()


def test_r90_first_leg_exports_without_receipt_or_next(records, tmp_path):
    simulator = ControllerSimulator(records, live=True, release_sha256=R90_RELEASE_SHA)
    try:
        host = ReviewedHoverLiveHost(simulator.client(), boot=BOOT,
            export_root=tmp_path, authorize_noncontact_motion=True,
            release_sha256=R90_RELEASE_SHA)
        result = host.run_first_leg_only()
        assert result["status"] == "FIRST_LEG_EXPORTED_AWAITING_RECEIPT"
        assert len(result["rows"]) == len(result["exports"]) == 1
        assert result["receipts_sent"] == 0
        assert result["continuation_allowed"] is False
        assert simulator.receipts == []
        assert [call[1].rsplit("/", 1)[-1] for call in simulator.calls] == [
            "start", "status", "record"]
        assert all(verify_export(Path(path))["valid"] for path in result["exports"])
        with pytest.raises(ValueError, match="consumed"):
            host.run_first_leg_only()
    finally:
        simulator.close()


def test_r90_first_leg_bad_record_faults_without_receipt(records, tmp_path):
    altered = records[:]
    bad = bytearray(altered[0]); bad[59] = 2; altered[0] = bytes(bad)
    simulator = ControllerSimulator(altered, live=True, release_sha256=R90_RELEASE_SHA)
    try:
        host = ReviewedHoverLiveHost(simulator.client(), boot=BOOT,
            export_root=tmp_path, authorize_noncontact_motion=True,
            release_sha256=R90_RELEASE_SHA)
        with pytest.raises(ValueError, match="Live campaign stopped; evidence:"):
            host.run_first_leg_only()
        assert simulator.receipts == []
        assert not any(call[1].endswith("/next") for call in simulator.calls)
        assert len(list(tmp_path.glob("wizard-*"))) == 2
    finally:
        simulator.close()


def test_r90_first_leg_persists_actual_sequence_after_polling(records, tmp_path):
    simulator = ControllerSimulator(records, live=True, release_sha256=R90_RELEASE_SHA,
                                    status_delay_polls=2)
    try:
        host = ReviewedHoverLiveHost(simulator.client(), boot=BOOT,
            export_root=tmp_path, authorize_noncontact_motion=True,
            release_sha256=R90_RELEASE_SHA)
        result = host.run_first_leg_only(pause=lambda _: None)
        assert result["authenticated_next_sequence"] == 5
        assert result["rows"][0]["authenticated_next_sequence"] == 5
        assert result["last_controller_status"] == "AWAITING_EXPORT|1"
        saved = Path(result["exports"][0])
        assert verify_export(saved)["valid"]
        assert json.loads((saved / "attachment-reviewed-hover-assessment.json")
                          .read_text())["authenticated_next_sequence"] == 5
        assert simulator.receipts == []
    finally:
        simulator.close()


def test_r90_a_cycle_stops_at_clear_without_fourth_receipt(records, tmp_path):
    simulator = ControllerSimulator(records, live=True, release_sha256=R90_RELEASE_SHA)
    try:
        host = ReviewedHoverLiveHost(simulator.client(), boot=BOOT,
            export_root=tmp_path, authorize_noncontact_motion=True,
            release_sha256=R90_RELEASE_SHA)
        result = host.run_a_cycle_only()
        assert result["status"] == "A_CYCLE_EXPORTED_AWAITING_RECEIPT"
        assert [row["pose_id"] for row in result["rows"]] == [
            "A_HOVER", "A_DOWN", "A_HOVER", "A_CLEAR"]
        assert result["receipts_sent"] == 3
        assert simulator.receipts == [1, 2, 3]
        assert result["authenticated_next_sequence"] == len(simulator.calls)
        assert not any(call[1].endswith("/next") and call[2] == b"5"
                       for call in simulator.calls)
        assert all(verify_export(Path(path))["valid"] for path in result["exports"])
    finally:
        simulator.close()


def test_live_runner_fault_stops_before_bad_record_receipt(records, tmp_path):
    altered = records[:]
    bad = bytearray(altered[7]); bad[59] = 2; altered[7] = bytes(bad)
    simulator = ControllerSimulator(altered, live=True)
    try:
        host = ReviewedHoverLiveHost(simulator.client(), boot=BOOT,
            export_root=tmp_path, authorize_noncontact_motion=True)
        with pytest.raises(ValueError, match="Live campaign stopped; evidence:"):
            host.run_once()
        assert simulator.receipts == list(range(1, 8))
        assert (tmp_path / f"reviewed-hover-live-{BOOT}.json").exists()
    finally:
        simulator.close()


def test_live_runner_lost_receipt_stops_without_next_or_retry(records, tmp_path):
    simulator = ControllerSimulator(records, fault=("lost_receipt", 8), live=True)
    try:
        host = ReviewedHoverLiveHost(simulator.client(), boot=BOOT,
            export_root=tmp_path, authorize_noncontact_motion=True)
        with pytest.raises(ValueError, match="Live campaign stopped; evidence:"):
            host.run_once()
        assert simulator.receipts == list(range(1, 9))
        assert host.session.stopped
        assert host.session.uncertainty["continuation_may_have_been_authorized"]
        assert simulator.calls[-1][1].endswith("/receipt")
        assert simulator.calls[-1][2].startswith(b"8:")
    finally:
        simulator.close()


def test_live_runner_rejects_read_only_resume_and_missing_permission(tmp_path):
    resumed = CharacterizationHTTP("127.0.0.1", 1, key=KEY, boot=BOOT,
        read_only_initial_sequence=1)
    with pytest.raises(ValueError, match="Fresh reviewed"):
        ReviewedHoverLiveHost(resumed, boot=BOOT, export_root=tmp_path,
            authorize_noncontact_motion=True)
    fresh = CharacterizationHTTP("127.0.0.1", 1, key=KEY, boot=BOOT,
        reviewed_hover_live_release_sha256=R89_RELEASE_SHA)
    with pytest.raises(ValueError, match="authorization"):
        ReviewedHoverLiveHost(fresh, boot=BOOT, export_root=tmp_path,
            authorize_noncontact_motion=False)
