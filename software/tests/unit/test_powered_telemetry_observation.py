"""Telemetry collector tests use only memory input, never the attached COM7."""

import base64
from threading import Event

import pytest

from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.powered_arm_feedback_contract import (
    PoweredFeedbackIntent, TELEMETRY_PURPOSE, TELEMETRY_LIMITS,
)
from rocell.providers.windows.powered_feedback_binding import PoweredFeedbackBinding
from rocell.providers.windows.nonpurging_serial_api import (
    IncapableWin32SerialApi, IncapableWin32Scenario, NativeSerialError, IoToken, FIXED_QUERY,
)
from rocell.providers.windows.powered_telemetry_observation import observe_rehearsal
from test_powered_feedback_observation import binding, REPLY


def telemetry_binding():
    query = binding()
    body = query.intent.to_dict()
    body.update(purpose=TELEMETRY_PURPOSE, limits=TELEMETRY_LIMITS)
    return PoweredFeedbackBinding(query.selection, PoweredFeedbackIntent(_canonical(body)))


def test_zero_write_contract_cannot_encode_or_increase_write_budget():
    selected = telemetry_binding()
    assert selected.intent.summary()["command_type"] is None
    with pytest.raises(ValueError, match="no outbound"):
        selected.intent.outbound_line
    body = selected.intent.to_dict()
    body["limits"]["maximum_write_attempts"] = 1
    with pytest.raises(ValueError, match="limits"):
        PoweredFeedbackIntent(_canonical(body))


def test_native_submission_guard_rejects_query_for_zero_write_intent(monkeypatch):
    from rocell.providers.windows.powered_feedback_serial_api import WindowsPoweredFeedbackSerialApi
    from rocell.providers.windows.nonpurging_serial_api import WindowsNativeSerialApi
    def forbidden(*args, **kwargs):
        pytest.fail("Native loader must not run")
    monkeypatch.setattr(WindowsNativeSerialApi, "_load_kernel", forbidden)
    api = WindowsPoweredFeedbackSerialApi("COM4096")
    # Test-only request injection exercises the final write guard, not admission.
    api._request = telemetry_binding().intent
    with pytest.raises(NativeSerialError, match="TELEMETRY_WRITES_FORBIDDEN"):
        api.submit_io(1, IoToken(2, "write", len(FIXED_QUERY), FIXED_QUERY))


def test_memory_capture_reads_existing_frames_without_writing():
    raw = b'partial}\n' + REPLY * 3 + b'{"T":'
    api = IncapableWin32SerialApi(IncapableWin32Scenario(startup_bytes=raw, read_fragment_bytes=7))
    result = observe_rehearsal(telemetry_binding(), api, Event())
    assert result["status"] == "CAPTURED_CLOSED", result
    assert result["capture"]["pose_sample_count"] == 3
    assert base64.b64decode(result["capture"]["raw"]["base64"]) == raw
    assert result["lifecycle"]["confirmed_write_bytes"] == 0
    assert result["lifecycle"]["write_consumed"] is False
    assert result["lifecycle"]["cleanup_confirmed"] is True
    assert result["late_cleanup_input"]["bytes"] == 0
    assert result['schema'] == 'rocell.powered_telemetry_observation.v3'
    assert result['started_monotonic_ns'] <= result['acquisition_started_monotonic_ns'] <= result['read_windows'][0][2]
    assert result['observation_finished_monotonic_ns'] - result['started_monotonic_ns'] >= 5_000_000_000


def test_silence_is_capture_not_feedback_success():
    result = observe_rehearsal(telemetry_binding(), IncapableWin32SerialApi(), Event())
    assert result["status"] == "CAPTURED_CLOSED"
    assert result["capture"]["pose_sample_count"] == 0
    assert result["capture"]["raw"]["bytes"] == 0
    assert result["connected"] is False


def test_query_and_telemetry_lifecycles_cannot_substitute_intents():
    from rocell.providers.windows.powered_feedback_observation import observe_rehearsal as query
    with pytest.raises(ValueError):
        observe_rehearsal(binding(), IncapableWin32SerialApi(), Event())
    with pytest.raises(ValueError):
        query(telemetry_binding(), IncapableWin32SerialApi(), Event())


def test_precancel_does_not_open():
    cancel = Event()
    cancel.set()
    result = observe_rehearsal(telemetry_binding(), IncapableWin32SerialApi(), cancel)
    assert result["status"] == "FAILED"
    assert result["lifecycle"]["open_consumed"] is False
    assert result['acquisition_started_monotonic_ns'] is None
