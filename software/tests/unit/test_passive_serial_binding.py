"""Execute the real lifecycle with passive identity and incapable Win32 calls."""

import json

import pytest

from rocell.application.passive_arm_identity import PassiveControllerSelection
from rocell.providers.windows.passive_serial_binding import PassiveSerialBinding
from rocell.providers.windows.nonpurging_serial_backend import (
    NonPurgingSerialConnection,
)
from rocell.providers.windows.nonpurging_serial_api import (
    IncapableWin32SerialApi,
    IncapableWin32Scenario,
    NativeSerialError,
    NATIVE_HOLD,
    FIXED_QUERY,
)
from test_wizard_native_arm_metadata import correlate, no_host_access


def binding(mode="rehearsal"):
    return PassiveSerialBinding(
        PassiveControllerSelection(json.dumps(correlate(mode=mode)).encode())
    )


def owner(**scenario):
    api = IncapableWin32SerialApi(IncapableWin32Scenario(**scenario))
    return NonPurgingSerialConnection(binding(), api=api), api


def test_passive_binding_has_no_fabricated_firmware_or_boot_fields():
    selected = binding()
    assert selected.identity.port_name == "COM91"
    assert len(selected.binding_sha256) == 64
    assert not hasattr(selected, "firmware_sha256")
    assert not hasattr(selected, "boot_policy_sha256")
    assert not hasattr(selected, "model_review_sha256")


def test_open_read_close_uses_no_write_event_or_query():
    connection, api = owner(startup_bytes=b"startup bytes\r\n")
    connection.open()
    assert connection.in_waiting == 15
    assert connection.read(15) == b"startup bytes\r\n"
    connection.close()
    status = connection.status()
    assert status["phase"] == "CLOSED"
    assert status["settings_readback_verified"] is True
    assert status["resource_counts"]["acquired"] == 2
    assert status["resource_counts"]["close_confirmed"] == 2
    assert status["confirmed_write_bytes"] == 0
    calls = [name for name, _ in api.trace]
    assert "create_event:2" not in calls
    assert "submit_write" not in calls


@pytest.mark.parametrize("payload", [b"", FIXED_QUERY, b'{"T":100}', None])
@pytest.mark.parametrize("phase", ["before", "open", "closed"])
def test_even_feedback_query_is_rejected_before_any_api_call(payload, phase):
    connection, api = owner()
    if phase in ("open", "closed"):
        connection.open()
    if phase == "closed":
        connection.close()
    trace = api.trace
    with pytest.raises(NativeSerialError, match="PASSIVE_WRITES_FORBIDDEN"):
        connection.write(payload)
    assert api.trace == trace
    connection.close()


def test_internal_io_admission_also_rejects_write():
    connection, api = owner()
    connection.open()
    trace = api.trace
    with pytest.raises(NativeSerialError, match="PASSIVE_WRITES_FORBIDDEN"):
        connection._io("write", len(FIXED_QUERY), FIXED_QUERY, 100)
    assert api.trace == trace
    connection.close()


@pytest.mark.parametrize(
    "failure",
    [
        "create_file",
        "create_event:1",
        "get_state",
        "set_state",
        "get_timeouts",
        "set_timeouts",
    ],
)
def test_partial_open_failures_cleanup_and_do_not_retry(failure):
    connection, api = owner(fail_operations=(failure,))
    with pytest.raises(NativeSerialError):
        connection.open()
    assert connection.status()["cleanup_confirmed"] is True
    trace = api.trace
    with pytest.raises(NativeSerialError, match="ONE_USE_CONNECTION"):
        connection.open()
    assert api.trace == trace


def test_uncertain_cleanup_is_retained_and_not_retried():
    connection, api = owner(fail_operations=("close_port",))
    connection.open()
    with pytest.raises(NativeSerialError):
        connection.close()
    assert connection.status()["cleanup_confirmed"] is False
    trace = api.trace
    with pytest.raises(NativeSerialError, match="CLEANUP_UNCONFIRMED"):
        connection.close()
    assert api.trace == trace


def test_native_binding_does_not_remove_existing_physical_hold():
    connection = NonPurgingSerialConnection(binding("physical"))
    with pytest.raises(NativeSerialError, match=NATIVE_HOLD):
        connection.open()
    assert connection.status()["resource_counts"]["acquired"] == 0


def test_physical_selection_cannot_use_incapable_api():
    with pytest.raises(NativeSerialError, match="ORIGIN_MISMATCH"):
        NonPurgingSerialConnection(binding("physical"), api=IncapableWin32SerialApi())
