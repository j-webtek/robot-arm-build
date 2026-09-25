"""Real Windows directory pins and file IO only; never a process or serial port."""
import os
import time
import pytest
from rocell.providers.windows._owned_worker_win32 import WindowsOwnedPassivePipeProcess
from rocell.application.physical_onboarding_durability import (
    publish_bytes, publish_reservation_bytes, PublicationMode, PhysicalOnboardingDurabilityError,
)
from test_positional_campaign_native_registration import prepared


@pytest.mark.skipif(os.name != 'nt', reason='Windows directory sharing contract')
def test_pinned_parent_rejects_rename_but_allows_verified_one_use_record(tmp_path):
    registration, _ = prepared(tmp_path)
    owner = WindowsOwnedPassivePipeProcess()
    try:
        owner.pin(registration)
        with pytest.raises(PhysicalOnboardingDurabilityError) as error:
            publish_bytes(tmp_path, 'rename-result.json', b'{"complete":true}',
                mode=PublicationMode.IMMUTABLE)
        assert 'MoveFileExW' in str(error.value)
        path = publish_reservation_bytes(tmp_path, 'reserved-result.json', b'{"complete":true}')
        assert path.read_bytes() == b'{"complete":true}'
    finally:
        assert owner.cleanup(time.monotonic_ns()+2_000_000_000) == ()


@pytest.mark.skipif(os.name != 'nt', reason='Windows directory sharing contract')
@pytest.mark.parametrize('mode', ['complete', 'miss'])
def test_actual_child_records_survive_real_parent_directory_pins(tmp_path, monkeypatch, mode):
    import json
    from test_positional_campaign_child_execution import prepared as child_fixture
    from rocell.providers.windows.positional_campaign_child_execution import _execute_authenticated_campaign_child
    reader, raw, kernel, cancellation, clock = child_fixture(tmp_path, monkeypatch, mode)
    runtime = tmp_path/'incapable-runtime'
    runtime.mkdir()
    registration, _ = prepared(runtime)
    owner = WindowsOwnedPassivePipeProcess()
    try:
        owner.pin(registration)  # Pins tmp_path too, just as the live parent does.
        compact = _execute_authenticated_campaign_child(raw, reader,
            cancellation=cancellation, clock_ns=lambda: clock[0])
        receipt = json.loads(compact)
        trial = json.loads((tmp_path/(reader.request.to_dict()['campaign_id']+'-native-trial.json')).read_bytes())
        assert trial['status'] == ('REPORTED_CAMPAIGN_COMPLETE' if mode=='complete' else 'HELD')
        assert receipt['trial_bytes'] > 0
        assert len(kernel.writes) == (2 if mode=='complete' else 1)
    finally:
        assert owner.cleanup(time.monotonic_ns()+2_000_000_000) == ()
