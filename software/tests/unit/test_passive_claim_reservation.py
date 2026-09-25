"""Reservation tails must block replay without weakening directory pins."""

import time

import pytest

from rocell.application.physical_onboarding_durability import (
    publish_reservation_bytes,
    PhysicalOnboardingDurabilityError,
    DurabilityCheckpoint,
)
from rocell.providers.windows._owned_worker_win32 import WindowsOwnedPassivePipeProcess


@pytest.mark.parametrize(
    "checkpoint",
    [
        DurabilityCheckpoint.AFTER_TEMP_CREATE,
        DurabilityCheckpoint.AFTER_TEMP_WRITE,
        DurabilityCheckpoint.AFTER_TEMP_FLUSH,
    ],
)
def test_interrupted_reservation_is_not_removed_or_reusable(tmp_path, checkpoint):
    def fail(actual):
        if actual == checkpoint.value:
            raise RuntimeError("modeled reservation interruption")

    with pytest.raises(RuntimeError):
        publish_reservation_bytes(
            tmp_path, "claim.json", b'{"reserved":true}', fault_injector=fail
        )
    path = tmp_path / "claim.json"
    assert path.is_file()
    before = path.read_bytes()
    with pytest.raises((PhysicalOnboardingDurabilityError, FileExistsError)):
        publish_reservation_bytes(tmp_path, "claim.json", b'{"replacement":true}')
    assert path.read_bytes() == before


def test_reservation_succeeds_with_original_directory_pin_policy(tmp_path):
    owner = WindowsOwnedPassivePipeProcess()
    try:
        owner._pin_directories({tmp_path})
        path = publish_reservation_bytes(tmp_path, "claim.json", b'{"reserved":true}')
        assert path.read_bytes() == b'{"reserved":true}'
    finally:
        assert owner.cleanup(time.monotonic_ns() + 2_000_000_000) == ()
