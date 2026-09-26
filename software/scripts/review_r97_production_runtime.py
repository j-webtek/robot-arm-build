"""Offline source and linked-image review for the r97 runtime candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from stage_r97_production_runtime import TARGET, sources


COMPILE_ID = "wizard-20260926T173219601251Z-d485be98eea84923b79039bc01b7dbe4"
APP_SHA = "7d2e47d40141e95b611fcf37ca38d495fcf3da4dc3051f128bbae95e10840d1d"


def review(root: Path) -> dict:
    root = Path(root).resolve()
    tools = root / ".firmware-tools"
    expected = sources(root)
    staged = tools / TARGET / "RoArm-M3_example"
    observed = {
        path.name: path.read_bytes() for path in staged.iterdir() if path.is_file()
    }
    if observed != expected:
        raise ValueError("r97 staged source differs")

    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    build = tools / "build-configured-diagnostic-candidate-r97--default-4mb-no-psram"
    app = (build / "RoArm-M3_example.ino.bin").read_bytes()
    report = json.loads(
        (root / "runs/wizard-exports" / COMPILE_ID /
         "attachment-compile-review.json").read_text(encoding="utf-8"))
    expected_source_hashes = {
        str((staged / name).relative_to(root)): sha(data)
        for name, data in expected.items()
    }
    for name, digest in expected_source_hashes.items():
        if report.get("source_hashes", {}).get(name) != digest:
            raise ValueError("r97 compile source binding differs")
    if (
        report.get("status") != "COMPILED"
        or report.get("target") != TARGET
        or report.get("build_profile") != "default-4mb-no-psram"
        or report.get("artifact_hashes", {}).get("RoArm-M3_example.ino.bin")
        != APP_SHA
        or sha(app) != APP_SHA
        or not 0 < len(app) <= 0x140000
    ):
        raise ValueError("r97 compile, artifact, or partition bounds differ")

    combined = b"\n".join(expected.values())
    if combined.count(b"SyncWritePosEx") != 1:
        raise ValueError("r97 group-write surface differs")
    for token in (
        b"WiFi", b"WebServer", b"LittleFS", b"Preferences", b"esp_now",
        b"serialCtrl", b"webCtrlServer", b"mission", b"servo_.WritePosEx(",
    ):
        if token in combined:
            raise ValueError(f"r97 excluded source surface present: {token!r}")
    for token in (
        b"SAFE_IDLE", b"startup_motion_commands", b"automatic_retry",
        b"TERMINAL_LOCKED", b"{\\\"T\\\":105}", b"esp_partition_get_sha256",
        b"configuration_epoch_sha256\\\":null",
    ):
        if token not in combined:
            raise ValueError(f"r97 required source surface absent: {token!r}")

    nm = tools / "data/packages/esp32/tools/esp-x32/2302/bin/xtensa-esp32-elf-nm.exe"
    symbols = subprocess.run(
        [str(nm), "-C", "--defined-only", str(build / "RoArm-M3_example.ino.elf")],
        check=True, capture_output=True, text=True, timeout=30,
    ).stdout
    for symbol in (
        "ProductionRuntimeV1::dispatchLine()",
        "ProductionRuntimeV1::acceptJointCommand()",
        "ProductionRuntimeV1::emitFeedback()",
        "SMS_STS::SyncWritePosEx",
        "SMS_STS::FeedBack",
    ):
        if symbol not in symbols:
            raise ValueError(f"r97 required linked symbol absent: {symbol}")
    for marker in (
        b"rocell.production_runtime.v1", b"ACCEPTED_ONCE",
        b"UNSUPPORTED_OR_MALFORMED_COMMAND", b"FEEDBACK_READ_FAILED",
    ):
        if marker not in app:
            raise ValueError(f"r97 required app marker absent: {marker!r}")

    return {
        "schema": "rocell.r97_production_runtime_review.v1",
        "status": "COMPILED_AWAITING_INDEPENDENT_REVIEW_NOT_INSTALLED",
        "app_sha256": APP_SHA,
        "compile_export_id": COMPILE_ID,
        "app_bytes": len(app),
        "app_offset": 0x10000,
        "app_slot_bytes": 0x140000,
        "startup_motion_commands": 0,
        "supported_commands": [102, 105],
        "supported_response": 1051,
        "maximum_command_bytes": 512,
        "group_write_call_sites": 1,
        "automatic_retry": False,
        "generic_vendor_dispatcher": False,
        "persistent_settings_access_from_sketch": False,
        "runtime_app_hash_attestation": True,
        "configuration_epoch_bound": False,
        "configuration_epoch_blocker": "UNBOUND_UNTIL_QUALIFIED_SESSION",
        "independent_review_complete": False,
        "hardware_access": False,
        "firmware_uploaded": False,
        "movement_command_sent": False,
        "physical_authority": False,
    }


if __name__ == "__main__":
    print(json.dumps(review(Path(__file__).resolve().parents[1]), indent=2))
