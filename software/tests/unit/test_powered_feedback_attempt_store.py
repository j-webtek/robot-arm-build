"""Real durable files with modeled arm originals; no device access."""

import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
import time

import pytest

from rocell.application import powered_feedback_attempt_store as store
from rocell.application.powered_arm_feedback_preparation import prepare_powered_feedback
from test_powered_arm_feedback_preparation import inputs
from test_wizard_native_arm_integration import setup


def journal(setup):
    values = inputs(setup)
    prepared = prepare_powered_feedback(**values)
    owner = store.PoweredFeedbackAttemptJournal(
        values["root"],
        prepared,
        startup_operation_id=values["startup_operation_id"],
        current_source_sha256=values["current_source_sha256"],
        now_monotonic_ns=time.monotonic_ns(),
    )
    return owner, values, prepared


def consume(owner, values):
    return owner.consume(
        current_source_sha256=values["current_source_sha256"],
        now_monotonic_ns=time.monotonic_ns(),
    )


def test_one_use_originals_and_raw_failed_outcome(setup):
    owner, values, prepared = journal(setup)
    receipt = consume(owner, values)
    assert receipt["physical_authority"] is receipt["replay_allowed"] is False
    with pytest.raises(ValueError, match="already consumed"):
        consume(owner, values)
    digest = owner.retain_outcome(
        stdout=b"malformed\xff", stderr=b"child failure", process_status="FAILED"
    )
    retained = store.collect_attempt(values["root"], receipt["attempt_id"])
    assert retained["chain_verified"] is retained["replay_allowed"] is False
    records = {}
    for item in retained["records"]:
        if item["status"] == "MISSING":
            continue
        raw = b"".join(
            base64.b64decode(chunk, validate=True) for chunk in item["base64_chunks"]
        )
        assert hashlib.sha256(raw).hexdigest() == item["sha256"]
        records[item["stage"]] = json.loads(raw)
    outcome = records["outcome"]["body"]
    assert digest == retained["records"][-1]["sha256"]
    assert base64.b64decode(outcome["stdout_base64"]) == b"malformed\xff"
    assert outcome["device_cleanup"] == "NOT_ESTABLISHED_BY_PROCESS_STATUS"
    assert outcome["consumption_sha256"] == receipt["consumption_sha256"]
    saved = records["prepared"]["body"]["originals_base64"]
    assert {name: base64.b64decode(raw) for name, raw in saved.items()} == dict(
        prepared.originals
    )
    with pytest.raises(ValueError, match="First outcome"):
        owner.retain_outcome(stdout=b"", stderr=b"", process_status="SUCCEEDED")


def test_two_concurrent_consumers_only_one_succeeds(setup):
    owner, values, _ = journal(setup)

    def attempt():
        try:
            return consume(owner, values)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: attempt(), range(2)))
    assert sum(result is not None for result in results) == 1


def test_reconstructed_owner_cannot_overwrite_attempt(setup):
    _, values, prepared = journal(setup)
    with pytest.raises(Exception):
        store.PoweredFeedbackAttemptJournal(
            values["root"],
            prepared,
            startup_operation_id=values["startup_operation_id"],
            current_source_sha256=values["current_source_sha256"],
            now_monotonic_ns=time.monotonic_ns(),
        )


@pytest.mark.parametrize("failure", ["source", "expired", "prepared", "startup"])
def test_changed_or_expired_evidence_burns_owner(setup, failure):
    owner, values, prepared = journal(setup)
    kwargs = dict(
        current_source_sha256=values["current_source_sha256"],
        now_monotonic_ns=time.monotonic_ns(),
    )
    if failure == "source":
        kwargs["current_source_sha256"] = "e" * 64
    elif failure == "expired":
        kwargs["now_monotonic_ns"] += 301_000_000_000
    elif failure == "prepared":
        store.attempt_path(
            values["root"], prepared.intent.to_dict()["attempt_id"], "prepared"
        ).write_bytes(b"changed")
    else:
        (
            values["root"]
            / (values["startup_operation_id"] + "-powered-startup-original.json")
        ).write_bytes(b"changed")
    with pytest.raises(ValueError):
        owner.consume(**kwargs)
    with pytest.raises(ValueError, match="already consumed"):
        consume(owner, values)


def test_partial_consumption_is_retained_and_not_retried(setup, monkeypatch):
    owner, values, prepared = journal(setup)
    calls = []

    def interrupted(root, name, raw, **kwargs):
        calls.append(name)
        (root / name).write_bytes(raw[:17])
        raise OSError("fixture interrupted write")

    monkeypatch.setattr(store, "publish_reservation_bytes", interrupted)
    with pytest.raises(OSError):
        consume(owner, values)
    with pytest.raises(ValueError, match="already consumed"):
        consume(owner, values)
    assert len(calls) == 1
    retained = store.collect_attempt(
        values["root"], prepared.intent.to_dict()["attempt_id"]
    )
    assert retained["records"][1]["bytes"] == 17
    assert retained["records"][2]["status"] == "MISSING"
    with pytest.raises(ValueError, match="First outcome"):
        owner.retain_outcome(stdout=b"", stderr=b"", process_status="UNKNOWN")


def test_dataclass_alone_cannot_bypass_original_validation(setup):
    values = inputs(setup)
    prepared = prepare_powered_feedback(**values)
    forged = replace(
        prepared, originals=prepared.originals + (("extra", b"not an original"),)
    )
    with pytest.raises(ValueError, match="association changed"):
        store.PoweredFeedbackAttemptJournal(
            values["root"],
            forged,
            startup_operation_id=values["startup_operation_id"],
            current_source_sha256=values["current_source_sha256"],
            now_monotonic_ns=time.monotonic_ns(),
        )


def test_existing_consumption_name_is_never_replaced(setup):
    owner, values, prepared = journal(setup)
    path = store.attempt_path(
        values["root"], prepared.intent.to_dict()["attempt_id"], "consumed"
    )
    path.write_bytes(b"partial previous consumption")
    with pytest.raises(Exception):
        consume(owner, values)
    assert path.read_bytes() == b"partial previous consumption"
    with pytest.raises(ValueError, match="already consumed"):
        consume(owner, values)


@pytest.mark.parametrize(
    "changes",
    [
        {"stdout": b"x" * (store.MAX_STDOUT_BYTES + 1)},
        {"stderr": b"x" * (store.MAX_STDERR_BYTES + 1)},
        {"process_status": "CONNECTED"},
        {"stdout": "not bytes"},
    ],
)
def test_invalid_outcome_cannot_be_retried_as_success(setup, changes):
    owner, values, _ = journal(setup)
    consume(owner, values)
    with pytest.raises(ValueError, match="Bounded raw"):
        owner.retain_outcome(
            **{"stdout": b"", "stderr": b"", "process_status": "UNKNOWN", **changes}
        )
    with pytest.raises(ValueError, match="First outcome"):
        owner.retain_outcome(stdout=b"", stderr=b"", process_status="SUCCEEDED")


@pytest.mark.parametrize("attempt", ["../escape", "operation-" + "a" * 33, "", None])
def test_recovery_rejects_non_service_ids(tmp_path, attempt):
    with pytest.raises(ValueError):
        store.collect_attempt(tmp_path, attempt)
