"""Entry association is not dispatch, authentication or electrical measurement."""

from copy import deepcopy
import hashlib
import json

import pytest

from rocell.application.arm_bench_qualification_contract import PassiveBenchRequest
from rocell.application.passive_arm_entry_policy import (
    PassiveEntryEvidence,
    SCHEMA,
    _FACTS,
    _REFS,
    MAX_SETUP_AGE_NS,
)
from test_arm_bench_qualification_contract import document


def prepared():
    request = document()
    request["mode"] = "physical"
    originals = {key: ("test-only original " + key).encode() for key in _REFS}
    refs = {key: hashlib.sha256(raw).hexdigest() for key, raw in originals.items()}
    request["references"].update(refs)
    evidence = {
        "schema": SCHEMA,
        "attempt_id": request["attempt_id"],
        "launch_id": request["launch_id"],
        "source_sha256": request["references"]["source_sha256"],
        "setup_confirmed_monotonic_ns": 1_000_000_000,
        "facts": dict(_FACTS),
        "references": refs,
    }
    return request, evidence, originals


def assess(request, evidence, originals, now=2_000_000_000):
    return PassiveEntryEvidence(json.dumps(evidence).encode()).assess(
        PassiveBenchRequest(json.dumps(request).encode()),
        originals,
        now_monotonic_ns=now,
    )


def test_matching_even_fabricated_bytes_never_claim_authentication():
    request, evidence, originals = prepared()
    before = deepcopy((request, evidence, originals))
    result = assess(request, evidence, originals)
    assert result["status"] == "ASSOCIATED_NOT_AUTHENTICATED"
    assert not result["blockers"]
    for key in (
        "references_authenticated",
        "physical_authority",
        "connected",
        "physical_dispatch_available",
    ):
        assert result[key] is False
    assert (request, evidence, originals) == before


@pytest.mark.parametrize("key", list(_FACTS))
def test_cannot_upgrade_or_omit_evidence_limitations(key):
    _, evidence, _ = prepared()
    evidence["facts"][key] = "MEASURED_OR_AUTHORIZED"
    with pytest.raises(ValueError):
        PassiveEntryEvidence(json.dumps(evidence).encode())
    del evidence["facts"][key]
    with pytest.raises(ValueError):
        PassiveEntryEvidence(json.dumps(evidence).encode())


@pytest.mark.parametrize("key", [k for k, v in _FACTS.items() if type(v) is bool])
def test_integer_cannot_impersonate_boolean(key):
    _, evidence, _ = prepared()
    evidence["facts"][key] = int(evidence["facts"][key])
    with pytest.raises(ValueError):
        PassiveEntryEvidence(json.dumps(evidence).encode())


@pytest.mark.parametrize("key", _REFS)
def test_changed_original_and_changed_request_are_separate_failures(key):
    request, evidence, originals = prepared()
    originals[key] += b" changed"
    assert (
        key.upper() + "_ORIGINAL_MISMATCH"
        in assess(request, evidence, originals)["blockers"]
    )
    request["references"][key] = "b" * 64
    assert (
        key.upper() + "_REQUEST_MISMATCH"
        in assess(request, evidence, originals)["blockers"]
    )


@pytest.mark.parametrize("key", ["attempt_id", "launch_id", "source_sha256"])
def test_rebinding_does_not_reuse_entry(key):
    request, evidence, originals = prepared()
    evidence[key] = "b" * 64
    assert assess(request, evidence, originals)["status"] == "HELD"


def test_no_rehearsal_promotion():
    request, evidence, originals = prepared()
    request["mode"] = "rehearsal"
    assert (
        "PHYSICAL_REQUEST_REQUIRED" in assess(request, evidence, originals)["blockers"]
    )


def test_setup_window_future_and_stale_are_held():
    request, evidence, originals = prepared()
    stamp = evidence["setup_confirmed_monotonic_ns"]
    assert (
        assess(request, evidence, originals, stamp + MAX_SETUP_AGE_NS)["blockers"] == []
    )
    for now in (stamp - 1, stamp + MAX_SETUP_AGE_NS + 1):
        assert (
            "SETUP_CONFIRMATION_STALE_OR_FUTURE"
            in assess(request, evidence, originals, now)["blockers"]
        )


@pytest.mark.parametrize(
    "payload",
    [b"", b"[]", b"null", b"x" * 32769, b'{"schema":1,"schema":2}', b"\xff"],
    ids=["empty", "array", "null", "large", "duplicate", "encoding"],
)
def test_bad_envelopes(payload):
    with pytest.raises(ValueError):
        PassiveEntryEvidence(payload)


def test_original_size_and_missing_originals():
    request, evidence, originals = prepared()
    originals[_REFS[0]] = b"x" * 32769
    assert assess(request, evidence, originals)["status"] == "HELD"
    del originals[_REFS[0]]
    with pytest.raises(ValueError):
        assess(request, evidence, originals)


def test_canonical_detached_evidence():
    _, evidence, _ = prepared()
    first = PassiveEntryEvidence(json.dumps(evidence).encode())
    second = PassiveEntryEvidence(
        json.dumps(evidence, indent=2, sort_keys=True).encode()
    )
    assert first.payload == second.payload
    evidence["facts"].clear()
    assert json.loads(first.payload)["facts"] == _FACTS
