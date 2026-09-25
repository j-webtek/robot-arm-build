"""Worker-claim filesystem tests; modeled metadata, no native device API."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import time

import pytest

from rocell.application import powered_feedback_child_claim as child
from rocell.application import powered_feedback_attempt_store as store
from rocell.application.physical_onboarding_durability import (
    PhysicalOnboardingDurabilityError,
)
from test_powered_feedback_attempt_store import journal, consume
from test_wizard_native_arm_integration import setup


def prepared_attempt(setup):
    owner, values, prepared = journal(setup)
    receipt = consume(owner, values)
    return owner, dict(
        root=values["root"],
        intent=prepared.intent,
        expected_consumption_sha256=receipt["consumption_sha256"],
        runtime_original=values["runtime_original"],
        current_source_sha256=values["current_source_sha256"],
        now_monotonic_ns=time.monotonic_ns(),
    )


def test_verify_is_read_only_and_live_claim_is_exact_one_use(setup):
    _, kwargs = prepared_attempt(setup)
    prepared = child.verify_consumed_attempt(**kwargs)
    path = store.attempt_path(
        kwargs["root"], kwargs["intent"].to_dict()["attempt_id"], "claimed"
    )
    assert not path.exists()
    claim = child.claim_for_child(**kwargs)
    assert claim.prepared == prepared
    with pytest.raises(ValueError, match="Live unconsumed"):
        child.consume_live_claim(replace(claim), kwargs["intent"])
    child.consume_live_claim(claim, kwargs["intent"])
    with pytest.raises(ValueError, match="Live unconsumed"):
        child.consume_live_claim(claim, kwargs["intent"])
    with pytest.raises(ValueError, match="already claimed"):
        child.claim_for_child(**kwargs)


def test_failed_intent_match_burns_live_claim(setup):
    _, kwargs = prepared_attempt(setup)
    claim = child.claim_for_child(**kwargs)
    with pytest.raises(ValueError, match="differs"):
        child.consume_live_claim(claim, None)
    with pytest.raises(ValueError, match="Live unconsumed"):
        child.consume_live_claim(claim, kwargs["intent"])


@pytest.mark.parametrize(
    "changed,value",
    [
        ("expected_consumption_sha256", "f" * 64),
        ("runtime_original", b"different worker"),
        ("current_source_sha256", "e" * 64),
    ],
)
def test_foreign_reference_cannot_claim(setup, changed, value):
    _, kwargs = prepared_attempt(setup)
    kwargs[changed] = value
    with pytest.raises(ValueError):
        child.claim_for_child(**kwargs)
    assert not store.attempt_path(
        kwargs["root"], kwargs["intent"].to_dict()["attempt_id"], "claimed"
    ).exists()


@pytest.mark.parametrize("stage", ["prepared", "consumed", "claimed", "outcome"])
def test_partial_record_never_qualifies_or_replays(setup, stage):
    _, kwargs = prepared_attempt(setup)
    store.attempt_path(
        kwargs["root"], kwargs["intent"].to_dict()["attempt_id"], stage
    ).write_bytes(b'{"partial":')
    with pytest.raises(ValueError):
        child.claim_for_child(**kwargs)


def test_concurrent_workers_have_one_winner(setup):
    _, kwargs = prepared_attempt(setup)

    def attempt():
        try:
            return child.claim_for_child(**kwargs)
        except (ValueError, OSError, PhysicalOnboardingDurabilityError):
            return None

    with ThreadPoolExecutor(max_workers=2) as workers:
        claims = list(workers.map(lambda _: attempt(), range(2)))
    winners = [claim for claim in claims if claim is not None]
    assert len(winners) == 1
    child.consume_live_claim(winners[0], kwargs["intent"])


def test_expired_consumption_cannot_be_claimed(setup):
    _, kwargs = prepared_attempt(setup)
    kwargs["now_monotonic_ns"] += 301_000_000_000
    with pytest.raises(ValueError, match="stale"):
        child.claim_for_child(**kwargs)
