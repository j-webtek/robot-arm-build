from threading import Event

import pytest
from rocell.application.positional_campaign_process_owner import run_campaign_process
from rocell.application.positional_campaign_native_export import verify_native_retained_export
from rocell.providers.windows.positional_campaign_native_protocol import decode_request
from rocell.providers.windows.nonpurging_serial_api import WindowsNativeSerialApi
from rocell.application.physical_onboarding_durability import PhysicalOnboardingDurabilityError
from test_positional_campaign_native_registration import prepared


def test_actual_parent_supervisor_retention_operation_reports_release_hold(tmp_path, monkeypatch):
    reg, raw = prepared(tmp_path)
    payload = decode_request(raw)['payload']
    def forbidden(*args):
        pytest.fail('Unqualified operation must not load serial kernel')
    monkeypatch.setattr(WindowsNativeSerialApi, '_load_kernel', forbidden)
    result = run_campaign_process(reg, payload, cancellation=Event(), clock_ns=lambda: 2_000_000_000)
    assert result['status'] == 'HELD'
    assert result['primary_error'] == 'CAMPAIGN_BOUNDED_ATTENDED_V2_REQUIRED'
    assert result['export_verified'] and not result['process_created']
    assert result['endpoint_diagnostics'] == []
    assert verify_native_retained_export(tmp_path, result['report_file'])['valid']
    with pytest.raises(PhysicalOnboardingDurabilityError):
        run_campaign_process(reg, payload, cancellation=Event(), clock_ns=lambda: 2_000_000_000)


def test_export_failure_cannot_rearm_parent_attempt(tmp_path, monkeypatch):
    reg, raw = prepared(tmp_path)
    payload = decode_request(raw)['payload']
    def failed(*args, **kwargs):
        raise OSError('Injected result storage failure')
    monkeypatch.setattr('rocell.application.positional_campaign_process_owner.publish_campaign_process_result', failed)
    with pytest.raises(OSError):
        run_campaign_process(reg, payload, cancellation=Event(), clock_ns=lambda: 2_000_000_000)
    with pytest.raises(PhysicalOnboardingDurabilityError):
        run_campaign_process(reg, payload, cancellation=Event(), clock_ns=lambda: 2_000_000_000)
