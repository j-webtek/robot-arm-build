"""Child-side original verification and exclusive claim before passive I/O.

An immutable claim prevents a second child claiming the same consumed intent.
This does not register a runtime or authorize native loading: those checks must
be supplied by the source-pinned parent/child composition. No device is opened.
"""

import base64
from dataclasses import dataclass
import hashlib
from threading import Lock

from .arm_bench_qualification_contract import PassiveBenchRequest, _canonical
from .passive_arm_entry_policy import PassiveEntryEvidence
from .passive_arm_attempt_store import inspect_attempt, _publish


@dataclass(frozen=True, slots=True)
class ClaimedPassiveAttempt:
    request: PassiveBenchRequest
    evidence: PassiveEntryEvidence
    claim_sha256: str


_LIVE_CLAIMS = {}
_LIVE_CLAIM_LOCK = Lock()


def consume_live_claim(claim, request):
    """Consume only the exact claim object issued in this process.

    A deserialized/copied receipt is not a live claim. Disk recovery cannot
    recreate this registration; parent source/worker checks remain mandatory.
    Consumption precedes native-admission checks, so failures cannot retry it.
    """
    with _LIVE_CLAIM_LOCK:
        if (
            type(claim) is not ClaimedPassiveAttempt
            or _LIVE_CLAIMS.get(claim.claim_sha256) is not claim
        ):
            raise ValueError("Live unconsumed child claim required")
        del _LIVE_CLAIMS[claim.claim_sha256]
    if (
        type(request) is not PassiveBenchRequest
        or request.payload != claim.request.payload
    ):
        raise ValueError("Native request differs from live claim")


def verify_consumed_attempt(
    *, root, request, expected_consumption_sha256, registration, now_monotonic_ns
):
    """Read and revalidate consumed originals without claiming or dispatching.

    Missing/unknown/changed evidence never implies permission to reconstruct or
    retry. A failure after publication leaves the claim consumed permanently.
    The caller's registration must already be independently source-validated;
    equality and hashes here associate it, not establish executable trust.
    """
    if (
        type(request) is not PassiveBenchRequest
        or request.to_dict()["mode"] != "physical"
    ):
        raise ValueError("Exact physical request required")
    request.require_time_available(now_monotonic_ns)
    body = request.to_dict()
    retained = inspect_attempt(root, body["attempt_id"])
    records = retained["records"]
    if records["prepared"] is None or records["consumed"] is None:
        raise ValueError("Prepared and consumed originals required")
    if records["claimed"] is not None or records["outcome"] is not None:
        raise ValueError("Attempt already claimed or completed; no replay")
    consumed = records["consumed"]
    consumption_sha = hashlib.sha256(_canonical(consumed)).hexdigest()
    if consumption_sha != expected_consumption_sha256:
        raise ValueError("Child consumption reference mismatch")
    consumption = consumed["body"]
    if (
        set(consumption)
        != {
            "prepared_sha256",
            "consumed_monotonic_ns",
            "request_sha256",
            "dispatch_may_have_started",
        }
        or consumption["request_sha256"] != request.request_sha256
        or consumption["dispatch_may_have_started"] is not True
        or type(consumption["consumed_monotonic_ns"]) is not int
        or not 0 < consumption["consumed_monotonic_ns"] <= now_monotonic_ns
    ):
        raise ValueError("Invalid consumption original")
    prepared = records["prepared"]["body"]
    if (
        set(prepared)
        != {
            "request",
            "entry_evidence_base64",
            "originals_base64",
            "registration",
            "references_authenticated_by_journal",
        }
        or prepared["references_authenticated_by_journal"] is not False
        or _canonical(prepared["request"]) != request.payload
    ):
        raise ValueError("Prepared request mismatch")
    if (
        type(registration) is not dict
        or _canonical(prepared["registration"]) != _canonical(registration)
        or hashlib.sha256(_canonical(registration)).hexdigest()
        != body["references"]["runtime_sha256"]
    ):
        raise ValueError("Child runtime differs from prepared registration")
    evidence = PassiveEntryEvidence(
        base64.b64decode(prepared["entry_evidence_base64"], validate=True)
    )
    if type(prepared["originals_base64"]) is not dict:
        raise ValueError("Entry originals required")
    originals = {
        key: base64.b64decode(value, validate=True)
        for key, value in prepared["originals_base64"].items()
    }
    if evidence.assess(request, originals, now_monotonic_ns=now_monotonic_ns)[
        "blockers"
    ]:
        raise ValueError("Child entry evidence association held")
    return evidence, consumption_sha


def claim_for_child(
    *, root, request, expected_consumption_sha256, registration, now_monotonic_ns
):
    """Revalidate at the child boundary, then publish one exclusive claim."""
    evidence, consumption_sha = verify_consumed_attempt(
        root=root,
        request=request,
        expected_consumption_sha256=expected_consumption_sha256,
        registration=registration,
        now_monotonic_ns=now_monotonic_ns,
    )
    body = request.to_dict()
    # Exclusive final-name reservation/readback is the one-winner boundary.
    # A partial record remains held: no delete, takeover or stale-claim recovery.
    claim_sha = _publish(
        root,
        body["attempt_id"],
        "claimed",
        {
            "consumption_sha256": consumption_sha,
            "request_sha256": request.request_sha256,
            "runtime_sha256": body["references"]["runtime_sha256"],
            "claimed_monotonic_ns": now_monotonic_ns,
            "native_access_granted": False,
        },
    )
    claimed = ClaimedPassiveAttempt(request, evidence, claim_sha)
    with _LIVE_CLAIM_LOCK:
        _LIVE_CLAIMS[claim_sha] = claimed
    return claimed
