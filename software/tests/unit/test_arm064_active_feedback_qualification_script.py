from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/run_arm064_active_feedback_qualification.ps1"


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_script_is_one_shot_and_exact_request_bound():
    text = source()
    assert "eyJUIjoxMDV9Cg==" in text
    assert "2cace64403a9db92d57acd8814d55c833529c0341468529900bd89f089e1fa3c" in text
    assert "$writeAttempts = 1" in text
    assert "$serialPort.Write($requestBytes, 0, $requestBytes.Length)" in text
    assert "$readAttempts = 1" in text
    assert "$openAttempts = 1" in text
    assert "$closeAttempts = 1" in text
    assert "while ($responseClock.Elapsed.TotalSeconds -lt 1.0)" in text


def test_script_denies_motion_retry_purge_fallback_and_control_lines():
    text = source()
    for literal in (
        "movement_commands = 0", "torque_commands = 0",
        "t102_commands = 0", "retry_count = 0", "purge_count = 0",
        "fallback_count = 0", "$serialPort.DtrEnable = $false",
        "$serialPort.RtsEnable = $false", "controller_start_performed = $false",
    ):
        assert literal in text
    for prohibited in (
        "DiscardInBuffer", "DiscardOutBuffer", "BaseStream.Flush",
        "T\":102", "T\":104", "while ($openAttempts", "while ($writeAttempts",
    ):
        assert prohibited not in text


def test_preflight_exits_before_serial_port_construction():
    text = source()
    preflight = text.index("if ($PreflightOnly)")
    construction = text.index("[System.IO.Ports.SerialPort]::new()")
    assert preflight < construction
    block = text[preflight:construction]
    assert "open_attempts = 0" in block
    assert "write_attempts = 0" in block
    assert "outbound_bytes = 0" in block


def test_live_path_writes_terminal_receipt_even_after_failure():
    text = source()
    assert "ACTIVE_FEEDBACK_FAILED_TERMINAL" in text
    assert "finally {" in text
    assert "$serialPort.Close()" in text
    assert "FileMode]::CreateNew" in text
    assert "Flush($true)" in text
