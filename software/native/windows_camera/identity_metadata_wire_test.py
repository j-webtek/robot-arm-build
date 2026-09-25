"""Pure CTest: native FakeApi serializer -> strict production Python parser.

Never invoke the production camera helper, even for inventory/identity. The
only accepted executable is the incapable native identity-metadata test target.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


def main() -> None:
    if len(sys.argv) != 2:
        raise RuntimeError("CTest must supply the fixed fake-only test executable")
    executable = Path(sys.argv[1]).resolve(strict=True)
    if executable.name != "rocell_identity_metadata_tests.exe":
        raise RuntimeError("Refusing a non-fixture executable")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from rocell.providers.windows.camera_worker_client import (
        bounded_subprocess_runner,
        parse_camera_identity_receipt,
    )

    process = bounded_subprocess_runner(
        (str(executable), "--emit-fixtures"), 5.0, 256 * 1024
    )
    assert process.returncode == 0 and not process.stderr
    assert not process.timed_out and not process.output_limit_exceeded
    fixtures = json.loads(process.stdout)
    assert isinstance(fixtures, list) and len(fixtures) == 31
    receipts = [
        parse_camera_identity_receipt(
            fixture,
            expected_endpoint="opaque-SYNTHETIC-endpoint",
            duration_ms=5000,
            max_parent_nodes=0 if index == 3 else 8,
        )
        for index, fixture in enumerate(fixtures)
    ]
    nominal = receipts[0]
    assert nominal.exact_endpoint_observed and not nominal.physical_authority
    assert nominal.device is not None
    assert nominal.protocol_schema == "rocell.windows_camera_identity.v2"
    assert (
        nominal.driver is not None and nominal.driver.devnode == nominal.device.devnode
    )
    assert nominal.driver.provider.value == "FIXTURE provider"
    assert nominal.driver.service.value == "FIXTURE service"
    assert nominal.driver.version.value == "1.2.3.4"
    assert nominal.driver.inf_path.value == "fixture.inf"
    assert (
        nominal.device.instance_id.value == r"USB\FIXTURE_CAMERA\uninterpreted-suffix"
    )
    assert nominal.device.container_id.value == "12345678-9abc-def0-0102-030405060708"
    assert [node.devnode for node in nominal.parents] == [2, 3]
    assert not nominal.parents[0].container_id.observed
    assert receipts[1].device is None and not receipts[1].exact_endpoint_observed
    assert receipts[2].chain_end == "PARENT_CYCLE"
    assert receipts[3].chain_end == "DEPTH_LIMIT" and not receipts[3].parents
    assert receipts[4].chain_end == receipts[5].chain_end == "PARENT_UNAVAILABLE"
    assert not receipts[6].exact_endpoint_observed
    assert receipts[7].device is not None
    assert (
        receipts[7].device.container_id.value == "00000000-0000-0000-0000-000000000000"
    )
    assert receipts[7].device.location_paths.value == ()
    assert receipts[8].api_calls == 0 and receipts[8].chain_end == "CANCELLED"
    assert receipts[25].chain_end == "REACHED_OBSERVED_ROOT"
    assert receipts[26].driver.provider.value is None
    assert receipts[26].driver.provider.error.native_code == 13
    assert receipts[26].driver.service.observed
    assert receipts[27].driver.version.error.reason == "WRONG_PROPERTY_TYPE"
    assert receipts[28].driver.inf_path.error.reason == "MALFORMED_VALUE"
    assert receipts[29].driver.provider.error.reason == "BYTE_LIMIT"
    assert receipts[30].driver.provider.error.reason == "NOT_REQUESTED"
    assert not receipts[30].exact_endpoint_observed
    for receipt in receipts[8:26]:
        if receipt.driver is not None:
            assert receipt.driver.devnode == receipt.devnode.value
    assert all(not receipt.physical_authority for receipt in receipts)
    print(
        "PASS: 31 native-fake to Python identity receipts; Windows metadata/camera calls: 0"
    )


if __name__ == "__main__":
    main()
