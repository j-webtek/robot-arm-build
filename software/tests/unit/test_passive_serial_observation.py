"""Exercise production lifecycle using memory Win32 results, never devices."""

import base64
import json
from threading import Event
from types import SimpleNamespace

import pytest

from rocell.application.arm_bench_qualification_contract import PassiveBenchRequest
from rocell.providers.windows import passive_serial_observation as module
from rocell.providers.windows.nonpurging_serial_api import (
    IncapableWin32SerialApi,
    IncapableWin32Scenario,
    WindowsNativeSerialApi,
)
from test_nonpurging_serial_backend import binding, forbid_native_loading
from test_arm_bench_qualification_contract import document


@pytest.fixture
def modeled_clock(monkeypatch):
    current = [1_000_000_000]

    def sleep(seconds):
        current[0] += round(seconds * 1_000_000_000)

    monkeypatch.setattr(
        module, "time", SimpleNamespace(monotonic_ns=lambda: current[0], sleep=sleep)
    )
    return current


def run(**scenario):
    api = IncapableWin32SerialApi(IncapableWin32Scenario(**scenario))
    result = module.observe_rehearsal(
        PassiveBenchRequest(json.dumps(document()).encode()), binding(), api, Event()
    )
    calls = [name for name, _ in api.trace]
    assert "submit_write" not in calls
    assert calls.count("create_file") == 1
    assert result["connected"] is result["physical_authority"] is False
    return result, api


@pytest.mark.parametrize(
    "startup",
    [b"", b"boot banner\r\n", b"x" * 65536],
    ids=["quiet", "banner", "capacity"],
)
def test_observation_retains_startup_without_feedback(modeled_clock, startup):
    result, api = run(startup_bytes=startup)
    assert result["summary"]["status"] == "OBSERVED_CLOSED"
    assert base64.b64decode(result["result"]["startup"]["base64"]) == startup
    assert result["result"]["observation_finished_monotonic_ns"] == 5_000_000_000
    assert not api.open_handles


@pytest.mark.parametrize(
    "fault",
    [
        "create_file",
        "create_event:1",
        "set_state",
        "get_timeouts",
        "submit_read",
        "close_port",
    ],
)
def test_failures_preserve_known_or_unknown_cleanup(modeled_clock, fault):
    result, api = run(startup_bytes=b"boot", fail_operations=(fault,))
    assert result["summary"]["status"] != "OBSERVED_CLOSED"
    assert result["result"]["errors"]
    if fault == "close_port":
        assert result["result"]["close_state"] == "UNKNOWN"
        assert api.open_handles
    else:
        assert not api.open_handles


def test_overflow_is_retained_as_incomplete(modeled_clock):
    result, api = run(startup_bytes=b"x" * 65537)
    assert result["result"]["startup"]["bytes"] == 65536
    assert result["result"]["startup"]["unretained_bytes"] == 1
    assert result["result"]["observation_complete"] is False
    assert api.remaining_input == b"x"


def test_stuck_pending_read_keeps_uncertain_resources(modeled_clock):
    result, api = run(
        startup_bytes=b"x",
        pending_kind="read",
        pending_outcome="timeout",
        cancel_outcome="stuck",
    )
    assert result["summary"]["status"] == "CLEANUP_UNCERTAIN"
    assert result["lifecycle"]["pending_io_unresolved"] is True
    assert result["result"]["startup"]["unretained_bytes"] is None
    assert api.open_handles


def test_late_cancelled_read_bytes_are_preserved(modeled_clock):
    result, _ = run(
        startup_bytes=b"late",
        pending_kind="read",
        pending_outcome="timeout",
        cancel_outcome="completed",
    )
    assert base64.b64decode(result["result"]["startup"]["base64"]) == b"late"
    assert result["result"]["observation_complete"] is False


def test_precancel_never_opens(modeled_clock):
    api = IncapableWin32SerialApi()
    cancel = Event()
    cancel.set()
    result = module.observe_rehearsal(
        PassiveBenchRequest(json.dumps(document()).encode()), binding(), api, cancel
    )
    assert api.trace == ()
    assert result["result"]["open_state"] == "NOT_ATTEMPTED"
    assert result["result"]["errors"] == ["CANCELLED"]


def test_real_clock_observation_uses_lifecycle_without_device_access():
    value = document()
    value["parent_deadline_monotonic_ns"] = module.time.monotonic_ns() + 10_000_000_000
    api = IncapableWin32SerialApi(
        IncapableWin32Scenario(startup_bytes=b"synthetic boot")
    )
    result = module.observe_rehearsal(
        PassiveBenchRequest(json.dumps(value).encode()), binding(), api, Event()
    )
    assert result["summary"]["status"] == "OBSERVED_CLOSED"
    assert (
        result["result"]["observation_finished_monotonic_ns"]
        - result["result"]["started_monotonic_ns"]
        >= module.OBSERVE_NS
    )
    assert not api.open_handles
    assert result["lifecycle"]["confirmed_write_bytes"] == 0


@pytest.mark.parametrize(
    "values", [{"state_mismatch": True}, {"timeout_mismatch": True}]
)
def test_settings_mismatch_cannot_report_observation_success(modeled_clock, values):
    result, api = run(**values)
    assert result["result"]["settings_verified"] is False
    assert result["result"]["observation_complete"] is False
    assert result["result"]["errors"] == ["CONFIGURATION_FAILED"]
    assert not api.open_handles


def test_poll_quota_terminates_even_without_clock_progress(modeled_clock):
    result, api = run(startup_bytes=b"x" * 2048, read_fragment_bytes=1)
    assert result["result"]["errors"] == ["OBSERVATION_FAILED"]
    assert result["result"]["startup"]["bytes"] == module.MAX_POLLS
    assert result["result"]["startup"]["unretained_bytes"] is None
    assert not api.open_handles


@pytest.mark.parametrize(
    "kind", ["native_api", "physical_request", "physical_binding", "expired"]
)
def test_ineligible_inputs_never_open(modeled_clock, kind):
    value = document()
    if kind == "physical_request":
        value["mode"] = "physical"
    if kind == "expired":
        value["parent_deadline_monotonic_ns"] = 2_000_000_000
    api = (
        WindowsNativeSerialApi() if kind == "native_api" else IncapableWin32SerialApi()
    )
    with pytest.raises(ValueError):
        module.observe_rehearsal(
            PassiveBenchRequest(json.dumps(value).encode()),
            binding(physical=kind == "physical_binding"),
            api,
            Event(),
        )
    if kind != "native_api":
        assert api.trace == ()
