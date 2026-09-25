"""Settings-only ceiling, unchanged permit lifetime; incapable native owner.

The coordinator clock is deliberately advanced without sleeping. Native
observations remain modeled; these tests establish deadline routing, not OS
scheduling or full-history performance.
"""

import pytest

from rocell.application.cell_commissioning_coordinator import (
    CAMERA_CONFIGURATION_MINIMUM_WINDOW_NS,
    MAX_PERMIT_TTL_NS,
)
from rocell.application.camera_activation_campaign_evidence import (
    validate_camera_activation_evidence,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.providers.windows.native_camera_activation_registration import (
    process_budget,
)
from test_physical_camera_activation_campaign import components
from test_camera_activation_application_handoff import no_device_calls
from test_native_camera_activation_supervisor import no_physical_owner


def test_configuration_floor_matches_unchanged_process_and_cleanup_budget():
    budget = process_budget("capture")
    assert (
        CAMERA_CONFIGURATION_MINIMUM_WINDOW_NS
        == (budget.run_timeout_ms + budget.cleanup_timeout_ms) * 1_000_000
    )
    assert MAX_PERMIT_TTL_NS == 30_000_000_000


@pytest.mark.parametrize(
    "configuration,remaining_ns,known",
    [
        (True, 24_000_000_000, True),
        (True, 16_999_999_999, False),
        (False, 24_000_000_000, False),
    ],
)
def test_only_settings_capture_can_use_sufficient_original_remaining_window(
    tmp_path, monkeypatch, configuration, remaining_ns, known
):
    worker, core, store, permit, owner, calls = components(
        tmp_path, monkeypatch, "capture", configuration_verification=configuration
    )
    expiry = permit.expires_at_ns
    monkeypatch.setattr(core, "_now", lambda: expiry - remaining_ns)
    result = core.execute(permit)
    assert permit.expires_at_ns == expiry
    assert permit.registration.budget.timeout_ms == 25_000
    if known:
        assert result.state is AttemptState.SEALED_KNOWN
        assert calls["owner"] == 1 and owner.cleaned
        observed = validate_camera_activation_evidence(worker.evidence)
        assert observed.run.to_dict()["parent_deadline_ns"] == expiry
    else:
        assert result.state is AttemptState.SEALED_UNCERTAIN
        assert result.quarantine_latched and result.receipt is None
        assert calls["owner"] == 0
        assert worker.evidence is None
    assert core.execute(permit) == result


@pytest.mark.parametrize(
    "remaining_ns,known", [(24_000_000_000, True), (16_999_999_999, False)]
)
def test_checksum_capture_uses_same_original_ceiling_and_lifecycle_floor(
    tmp_path, monkeypatch, remaining_ns, known
):
    from test_camera_sealed_capture_campaign import setup

    worker, core, store, permit, owner, calls, path = setup(tmp_path, monkeypatch)
    expiry = permit.expires_at_ns
    monkeypatch.setattr(core, "_now", lambda: expiry - remaining_ns)
    result = core.execute(permit)
    assert (
        permit.expires_at_ns == expiry
        and permit.registration.budget.timeout_ms == 25_000
    )
    assert calls["owner"] == int(known)
    if known:
        assert result.state is AttemptState.SEALED_KNOWN
        assert worker.evidence.checksum.to_dict()["deadline_ns"] == expiry
        assert owner.cleaned and path.is_file()
    else:
        assert (
            result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
        )
        assert worker.evidence is None and not path.exists()
    assert core.execute(permit) == result and calls["owner"] == int(known)
