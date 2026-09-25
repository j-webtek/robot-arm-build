"""Native facade restrictions with every DLL load forbidden."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from rocell.providers.windows.passive_serial_api import WindowsPassiveSerialApi
from rocell.providers.windows.nonpurging_serial_api import (
    IoToken,
    FIXED_QUERY,
    NativeSerialError,
    WindowsNativeSerialApi,
    NATIVE_HOLD,
)
from rocell.providers.windows.nonpurging_serial_backend import (
    NonPurgingSerialConnection,
)
from test_nonpurging_serial_backend import (
    forbid_native_loading,
    binding as feedback_binding,
)
from test_passive_serial_binding import binding


@pytest.mark.parametrize(
    "port", ["COM0", "COM4097", "com6", "COM6 ", "COM6/other", "\\\\.\\COM6", None]
)
def test_no_arbitrary_endpoint(port):
    with pytest.raises(NativeSerialError):
        WindowsPassiveSerialApi(port)


def test_correct_endpoint_remains_held_and_cannot_be_reopened():
    api = WindowsPassiveSerialApi("COM91")
    assert api.status()["native_api_loaded"] is False
    with pytest.raises(NativeSerialError, match=NATIVE_HOLD):
        api.create_file(r"\\.\COM91")
    with pytest.raises(NativeSerialError, match="ONE_USE_PASSIVE_API"):
        api.create_file(r"\\.\COM91")


def test_wrong_path_consumes_attempt_before_any_native_call():
    api = WindowsPassiveSerialApi("COM91")
    with pytest.raises(NativeSerialError, match="PASSIVE_ENDPOINT_CHANGED"):
        api.create_file(r"\\.\COM92")
    with pytest.raises(NativeSerialError, match="ONE_USE_PASSIVE_API"):
        api.create_file(r"\\.\COM91")


@pytest.mark.parametrize("method", ["submit_io", "complete_io", "cancel_io"])
def test_write_rejected_at_all_native_io_entrypoints(method):
    api = WindowsPassiveSerialApi("COM91")
    token = IoToken(1, "write", len(FIXED_QUERY), FIXED_QUERY)
    args = (1, token, 10) if method == "complete_io" else (1, token)
    with pytest.raises(NativeSerialError, match="PASSIVE_WRITES_FORBIDDEN"):
        getattr(api, method)(*args)
    assert token.submitted is False and token.storage is None


def test_read_token_with_outbound_payload_is_also_rejected():
    api = WindowsPassiveSerialApi("COM91")
    with pytest.raises(NativeSerialError, match="PASSIVE_WRITES_FORBIDDEN"):
        api.submit_io(1, IoToken(1, "read", 1, b"x"))


def test_concurrent_opens_attempt_native_load_only_once():
    api = WindowsPassiveSerialApi("COM91")

    def run(_):
        try:
            api.create_file(r"\\.\COM91")
        except NativeSerialError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = list(pool.map(run, range(4)))
    assert codes.count(NATIVE_HOLD) == 1
    assert codes.count("ONE_USE_PASSIVE_API") == 3


def test_passive_binding_requires_passive_native_api():
    with pytest.raises(NativeSerialError, match="UNREGISTERED_NATIVE_API"):
        NonPurgingSerialConnection(binding("physical"), api=WindowsNativeSerialApi())
    with pytest.raises(NativeSerialError, match="PASSIVE_ENDPOINT_CHANGED"):
        NonPurgingSerialConnection(
            binding("physical"), api=WindowsPassiveSerialApi("COM92")
        )


def test_feedback_binding_cannot_use_passive_native_api():
    with pytest.raises(NativeSerialError, match="UNREGISTERED_NATIVE_API"):
        NonPurgingSerialConnection(
            feedback_binding(physical=True), api=WindowsPassiveSerialApi("COM404")
        )
