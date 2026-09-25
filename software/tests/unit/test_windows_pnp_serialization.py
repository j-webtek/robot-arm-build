"""Real Windows PowerShell serialization with in-memory PnP fixtures only.

The production script runs, but both PnP commands are local fixture functions
and module autoloading is disabled. No host inventory or device API is called.
This catches array unrolling that JSON-only Python fixtures cannot reproduce.
"""

import json
import shutil
import subprocess
from typing import Any

import pytest

from rocell.application.physical_device_inventory import (
    ArgvCommandResult,
    PhysicalDeviceInventoryError,
    WINDOWS_CAMERA_PNP_ARGV,
    inventory_windows_pnp_cameras,
)
from test_physical_device_inventory import _RecordingRunner, _windows_record


_FIXTURE_PROVIDER = r"""
$ErrorActionPreference = 'Stop'
$PSModuleAutoLoadingPreference = 'None'
Import-Module Microsoft.PowerShell.Utility -ErrorAction Stop
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
$script:FixtureDevices = ConvertFrom-Json -InputObject ([Console]::In.ReadToEnd())
function Get-PnpDevice {
  param([switch]$PresentOnly)
  if (-not $PresentOnly) { throw 'Fixture requires PresentOnly' }
  $script:FixtureDevices
}
function Get-PnpDeviceProperty {
  param($InstanceId, $KeyName, $ErrorAction)
  $matches = @($script:FixtureDevices | Where-Object { $_.InstanceId -eq $InstanceId })
  if ($matches.Count -ne 1) { throw 'Ambiguous fixture instance' }
  $field = switch ($KeyName) {
    'DEVPKEY_Device_Manufacturer' { 'Manufacturer' }
    'DEVPKEY_Device_BusReportedDeviceDesc' { 'Product' }
    'DEVPKEY_Device_Service' { 'Service' }
    'DEVPKEY_Device_SerialNumber' { 'SerialNumber' }
    'DEVPKEY_Device_ContainerId' { 'ContainerId' }
    'DEVPKEY_Device_HardwareIds' { 'HardwareIds' }
    default { throw 'Unregistered fixture property' }
  }
  [pscustomobject]@{ Data = $matches[0].$field }
}
"""


def _serialize(records: list[dict[str, Any]]) -> ArgvCommandResult:
    executable = shutil.which("powershell.exe")
    if executable is None:
        pytest.skip("Windows PowerShell unavailable; no hardware fallback")
    # The fixed prefix supplies all PnP observations. Only the bundled Utility
    # module is imported; absent fixture functions cannot autoload PnpDevice.
    completed = subprocess.run(
        [
            executable,
            *WINDOWS_CAMERA_PNP_ARGV[1:-1],
            _FIXTURE_PROVIDER + WINDOWS_CAMERA_PNP_ARGV[-1],
        ],
        input=json.dumps(records).encode("ascii"),
        capture_output=True,
        timeout=15,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    assert completed.stderr == b""
    return ArgvCommandResult(completed.returncode, completed.stdout, completed.stderr)


class RetainedOutputRunner:
    """Hand already-created fixture bytes to the unmodified production decoder."""

    def __init__(self, result: ArgvCommandResult) -> None:
        self.result = result
        self.calls = 0

    def run(self, argv: tuple[str, ...], *, timeout_seconds: int) -> ArgvCommandResult:
        assert argv == WINDOWS_CAMERA_PNP_ARGV
        self.calls += 1
        return self.result


@pytest.mark.parametrize("count", [0, 1, 2])
def test_real_powershell_always_emits_array_and_decoder_keeps_candidate_count(count):
    records = [
        _windows_record(
            name=f"OFFLINE camera {index}",
            instance_id=f"USB\\VID_52CB&PID_0477\\FIXTURE-{index}",
            serial_number=f"FIXTURE-{index}",
        )
        for index in range(count)
    ]
    encoded = _serialize(records)
    # A one-value HardwareIds property is allowed to unwrap by the existing
    # property helper. The decoder already accepts that string-or-array field;
    # the top-level inventory must always remain an array of records.
    assert json.loads(encoded.stdout) == [
        {**record, "HardwareIds": record["HardwareIds"][0]} for record in records
    ]
    runner = RetainedOutputRunner(encoded)
    batch = inventory_windows_pnp_cameras(runner)
    assert len(batch.candidates) == count
    assert batch.collection_complete is True
    assert runner.calls == 1


def test_real_script_preserves_missing_serial_unicode_and_filters_non_cameras():
    camera = _windows_record(name="OFFLINE cam\u00e9ra", serial_number=None)
    other = _windows_record(instance_id="FIXTURE-PORT")
    other["Class"] = "Ports"
    runner = RetainedOutputRunner(_serialize([camera, other]))
    batch = inventory_windows_pnp_cameras(runner)
    assert len(batch.candidates) == 1
    assert batch.candidates[0].display_name == "OFFLINE cam\u00e9ra"
    assert batch.candidates[0].unit_serial is None
    assert "CAMERA_UNIT_SERIAL_MISSING" in batch.candidates[0].identity_blockers


def test_real_script_retains_over_limit_sentinel_for_strict_decoder():
    records = [_windows_record(instance_id=f"FIXTURE-{index}") for index in range(130)]
    encoded = _serialize(records)
    assert len(json.loads(encoded.stdout)) == 129
    batch = inventory_windows_pnp_cameras(RetainedOutputRunner(encoded))
    assert not batch.collection_complete
    assert batch.candidates == ()
    assert batch.collection_blockers == ("WINDOWS_PNP_CANDIDATE_LIMIT_EXCEEDED",)


@pytest.mark.parametrize("document", [{}, None, "bad", 1, False])
def test_fix_does_not_relax_decoder_to_accept_non_array_roots(document):
    runner = _RecordingRunner(document)
    with pytest.raises(PhysicalDeviceInventoryError, match="root must be an array"):
        inventory_windows_pnp_cameras(runner)
    assert len(runner.calls) == 1
