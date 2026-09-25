"""Durable child handoff tests on temporary disk, never an actual child/device."""

import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest

from rocell.application.arm_bench_qualification_contract import (
    PassiveBenchRequest,
    _canonical,
)
from rocell.application.passive_arm_entry_policy import PassiveEntryEvidence
from rocell.application.passive_arm_attempt_store import (
    PassiveAttemptJournal,
    inspect_attempt,
)
from rocell.application.passive_arm_child_claim import claim_for_child
from rocell.application.physical_onboarding_durability import (
    PhysicalOnboardingDurabilityError,
)
from test_passive_arm_entry_policy import prepared


def entry(root, consume=True):
    raw, evidence, originals = prepared()
    raw["attempt_id"] = evidence["attempt_id"] = "operation-" + "e" * 32
    registration = {"fixture": "NOT A REGISTERED NATIVE WORKER"}
    raw["references"]["runtime_sha256"] = hashlib.sha256(
        _canonical(registration)
    ).hexdigest()
    request = PassiveBenchRequest(_canonical(raw))
    journal = PassiveAttemptJournal(
        root,
        request,
        PassiveEntryEvidence(_canonical(evidence)),
        originals,
        registration,
        now_monotonic_ns=2_000_000_000,
    )
    receipt = journal.consume(now_monotonic_ns=3_000_000_000) if consume else None
    return journal, dict(
        root=root,
        request=request,
        expected_consumption_sha256=(
            receipt["consumption_sha256"] if receipt else "a" * 64
        ),
        registration=registration,
        now_monotonic_ns=4_000_000_000,
    )


def test_child_claim_verifies_and_prevents_second_claim(tmp_path):
    _, values = entry(tmp_path)
    claim = claim_for_child(**values)
    assert claim.request == values["request"]
    history = inspect_attempt(tmp_path, claim.request.to_dict()["attempt_id"])
    assert history["status"] == "OUTCOME_UNKNOWN_NO_REPLAY"
    assert history["records"]["claimed"]["body"]["native_access_granted"] is False
    with pytest.raises(ValueError, match="already claimed"):
        claim_for_child(**values)


def test_only_one_concurrent_child_claim_wins(tmp_path):
    _, values = entry(tmp_path)

    def claim(_):
        try:
            claim_for_child(**values)
            return True
        except (ValueError, PhysicalOnboardingDurabilityError):
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(claim, range(4))).count(True) == 1


def test_prepared_but_unconsumed_cannot_be_claimed(tmp_path):
    _, values = entry(tmp_path, consume=False)
    with pytest.raises(ValueError, match="consumed originals"):
        claim_for_child(**values)


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_consumption_sha256", "b" * 64),
        ("registration", {"other": "runtime"}),
        ("now_monotonic_ns", 2_500_000_000),
        ("now_monotonic_ns", 19_000_000_000),
    ],
)
def test_mismatched_or_late_handoff_rejected_before_claim(tmp_path, field, value):
    _, values = entry(tmp_path)
    values[field] = value
    with pytest.raises(ValueError):
        claim_for_child(**values)
    assert (
        inspect_attempt(tmp_path, values["request"].to_dict()["attempt_id"])["records"][
            "claimed"
        ]
        is None
    )


def test_completed_attempt_cannot_start_a_child(tmp_path):
    journal, values = entry(tmp_path)
    journal.retain_outcome(stdout=b"", stderr=b"", process_status="FAILED")
    with pytest.raises(ValueError, match="completed"):
        claim_for_child(**values)
