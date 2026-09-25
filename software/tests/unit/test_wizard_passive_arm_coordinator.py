"""Public setup to coordinator, cancelled before native child creation."""

from threading import Event

import pytest

from rocell.application import wizard_passive_arm_coordinator as coordinator
from rocell.application.passive_arm_attempt_store import (
    inspect_attempt,
    PassiveAttemptJournal,
)
from test_passive_arm_preparation import prepared_inputs
from test_wizard_native_arm_integration import setup


def inputs(setup):
    _, _, values = prepared_inputs(setup)
    values.pop("registration")
    values.pop("now_monotonic_ns")
    cancel = Event()
    cancel.set()
    values.update(cancellation=cancel, check_current=lambda: None)
    return values


def test_public_setup_cancelled_attempt_is_retained_and_not_replayable(setup):
    values = inputs(setup)
    owner = coordinator.PassiveArmCoordinator()
    result = owner.run(**values)
    assert not result.process.process_created
    assert result.outcome_sha256 and result.persistence_error is None
    assert result.summary()["connected"] is False
    retained = inspect_attempt(values["root"], values["attempt_id"])
    assert retained["status"] == "OUTCOME_RETAINED_NOT_DEVICE_ACCEPTANCE"
    assert retained["records"]["claimed"] is None
    with pytest.raises(ValueError, match="already consumed"):
        owner.run(**values)


def test_failed_log_publication_returns_raw_process_result(setup, monkeypatch):
    values = inputs(setup)

    def fail(*args, **kwargs):
        raise OSError("fixture full disk")

    monkeypatch.setattr(PassiveAttemptJournal, "retain_outcome", fail)
    result = coordinator.PassiveArmCoordinator().run(**values)
    assert result.outcome_sha256 is None
    assert result.persistence_error == "OSError"
    assert type(result.process.stdout) is bytes
    assert type(result.process.stderr) is bytes
    assert result.summary()["status"] == "OUTCOME_PERSISTENCE_FAILED"
    assert (
        inspect_attempt(values["root"], values["attempt_id"])["status"]
        == "OUTCOME_UNKNOWN_NO_REPLAY"
    )


def test_changed_service_state_prevents_consumption_and_dispatch(setup):
    values = inputs(setup)
    checks = []

    def check():
        checks.append(1)
        if len(checks) == 2:
            raise ValueError("fixture source changed")

    values["check_current"] = check
    with pytest.raises(ValueError, match="source changed"):
        coordinator.PassiveArmCoordinator().run(**values)
    history = inspect_attempt(values["root"], values["attempt_id"])
    assert history["status"] == "PREPARED_NOT_REPLAYABLE"
    assert history["records"]["consumed"] is None


def test_foreign_receipt_fails_without_consumption(setup):
    values = inputs(setup)
    values["expected_setup_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="differs from service receipt"):
        coordinator.PassiveArmCoordinator().run(**values)
    assert (
        inspect_attempt(values["root"], values["attempt_id"])["status"] == "NO_ATTEMPT"
    )
