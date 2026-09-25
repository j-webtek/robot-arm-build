from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application.air_typing_b_hover import assess_record, BHoverHost
from rocell.application.wizard_diagnostic_export import verify_export


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / ".firmware-tools/configured-diagnostic-candidate-r76/RoArm-M3_example"


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Native compiler unavailable")
    target = tmp_path_factory.mktemp("r76-native") / "owner.exe"
    result = subprocess.run([compiler, "-std=c++17", "-O2", "-I" + str(STAGE),
        "-I" + str(ROOT / "firmware/diagnostics"),
        str(ROOT / "firmware/diagnostics/test_air_typing_r76_owner.cpp"),
        "-o", str(target)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return target


@pytest.mark.parametrize("mode", ["delivery", "wrong_endpoint", "passive_drift",
                                      "evidence", "source", "prewrite", "stale", "timeout"])
def test_faults_stop_without_success(native, mode):
    result = subprocess.run([str(native), mode], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, (mode, result.returncode, result.stderr)


def test_one_leg_replays_independently_and_exports(native, tmp_path):
    result = subprocess.run([str(native), "success"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    raw = bytes.fromhex(result.stdout.strip())
    row = assess_record(raw, boot="ab" * 16)
    assert row["status"] == "B_HOVER_JOINT_ENDPOINT_VERIFIED"
    assert row["physical_accuracy_verified"] is False

    class Transport:
        def __init__(self):
            self.receipts = 0
        def __call__(self, method, path, body=b""):
            suffix = path.rsplit("/", 1)[-1]
            if suffix == "start":
                assert method == "POST" and body == b"AIRB1"
                return b"CAPTURING_START"
            if suffix == "status":
                return b"AWAITING_EXPORT|1"
            if suffix == "record":
                return raw.hex().encode()
            if suffix == "receipt":
                assert body == f'1:{row["record_sha256"]}'.encode()
                self.receipts += 1
                return b"COMPLETE"
            raise AssertionError(path)

    transport = Transport()
    host = BHoverHost(transport, boot="ab" * 16, export_root=tmp_path,
                      source_kind="simulation")
    result = host.run_once()
    assert result["status"] == "B_HOVER_COMPLETE"
    assert transport.receipts == 1
    assert verify_export(Path(result["export"]))["valid"]
    with pytest.raises(ValueError, match="consumed"):
        host.run_once()


@pytest.mark.parametrize("change", ["domain", "target", "boot", "position"])
def test_record_tampering_never_verifies(native, change):
    result = subprocess.run([str(native), "success"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    raw = bytearray.fromhex(result.stdout.strip())
    if change == "domain":
        raw[0] ^= 1
    elif change == "target":
        raw[28] ^= 1
    elif change == "boot":
        raw[10] ^= 1
    else:
        # First source servo position in retained record.
        raw[54] ^= 1
    with pytest.raises(ValueError):
        assess_record(bytes(raw), boot="ab" * 16)


def test_authenticated_route_core_is_one_use(tmp_path):
    compiler = shutil.which("clang++")
    if not compiler:
        pytest.skip("Native compiler unavailable")
    source = (ROOT / "firmware/diagnostics/test_air_typing_routes.cpp").read_text()
    changes = {
        "#include \"air_typing_routes.h\"": "#include <air_typing_routes.h>",
        "{2047,2225,1890,2716,1979,2041,2047}": "{1949,2082,2033,2600,2235,2041,2047}",
        "{2047,2217,1897,2711,1980,2040,2047}": "{1941,2080,2034,2591,2236,2040,2047}",
        "{0,8,-7,5,-1,1,0}": "{8,2,-1,9,-1,1,0}",
        "/rocell/air-type/": "/rocell/air-type-b-hover/",
        "AIR17": "AIRB1",
    }
    for old, new in changes.items():
        assert old in source
        source = source.replace(old, new)
    target = tmp_path / "routes.exe"
    result = subprocess.run([compiler, "-std=c++17", "-O2", "-x", "c++", "-",
        "-I" + str(STAGE), "-I" + str(ROOT / "firmware/diagnostics"),
        "-o", str(target)], input=source, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    result = subprocess.run([str(target)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, (result.returncode, result.stderr)
