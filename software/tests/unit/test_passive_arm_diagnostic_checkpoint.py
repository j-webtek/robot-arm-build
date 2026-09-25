"""Bounded, immutable historical diagnostic retention, without device effects."""

import json
import hashlib
import pytest

from rocell.application.passive_arm_diagnostic_checkpoint import publish, recover
from rocell.application.passive_arm_diagnostic_checkpoint import (
    publish_intent,
    read_intent,
    recover_attempt,
    encoded,
)
from test_arm_bench_qualification_contract import document

SESSION = "wizard-" + "a" * 32


def retained():
    return dict(
        operation_id="operation-" + "b" * 32,
        source_sha256="c" * 64,
        result={"raw": "unchanged", "status": "FAILED"},
        physical_authority=False,
    )


def test_immutable_recovery(tmp_path):
    receipt = publish(tmp_path, SESSION, retained())
    path = tmp_path / (SESSION + "-passive.json")
    result = recover(path)
    assert result["retained"] == retained()
    assert receipt["sha256"] == result["sha256"]
    assert result["authenticated"] is result["qualified"] is False
    before = path.read_bytes()
    with pytest.raises(Exception):
        publish(tmp_path, SESSION, retained())
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "damage", ["truncate", "tamper", "duplicate", "oversize", "rename"]
)
def test_invalid_checkpoint_is_never_recovered(tmp_path, damage):
    publish(tmp_path, SESSION, retained())
    path = tmp_path / (SESSION + "-passive.json")
    raw = path.read_bytes()
    if damage == "truncate":
        path.write_bytes(raw[:50])
    elif damage == "tamper":
        path.write_bytes(raw.replace(b"unchanged", b"corrupted"))
    elif damage == "duplicate":
        path.write_bytes(b'{"schema":"duplicate",' + raw[1:])
    elif damage == "oversize":
        path.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    else:
        path = path.rename(tmp_path / ("wizard-" + "d" * 32 + "-passive.json"))
    with pytest.raises(Exception):
        recover(path)


def test_missing_file_is_not_an_empty_success(tmp_path):
    with pytest.raises(Exception):
        recover(tmp_path / (SESSION + "-passive.json"))


def intent(tmp_path):
    request = document()
    request["launch_id"] = SESSION
    request["attempt_id"] = retained()["operation_id"]
    registration = {"synthetic": True}
    request["references"]["runtime_sha256"] = hashlib.sha256(
        encoded(registration)
    ).hexdigest()
    return publish_intent(
        tmp_path, SESSION, request, registration, {"request": request}
    )


def test_intent_without_outcome_remains_unknown_and_cannot_be_replaced(tmp_path):
    receipt = intent(tmp_path)
    observed = recover_attempt(tmp_path, SESSION)
    assert observed["intent"] == receipt["record"]
    assert observed["status"] == "OUTCOME_UNKNOWN_NO_REPLAY"
    assert observed["replay_allowed"] is False
    with pytest.raises(Exception):
        intent(tmp_path)


def test_unrelated_outcome_is_retained_but_not_paired(tmp_path):
    intent(tmp_path)
    publish(tmp_path, SESSION, retained())
    observed = recover_attempt(tmp_path, SESSION)
    assert observed["status"] == "OUTCOME_UNBOUND_NO_REPLAY"
    assert observed["outcome"] is not None


def test_damaged_intent_blocks_pair_readback(tmp_path):
    intent(tmp_path)
    path = tmp_path / (SESSION + "-passive-intent.json")
    path.write_bytes(path.read_bytes()[:30])
    with pytest.raises(Exception):
        recover_attempt(tmp_path, SESSION)
