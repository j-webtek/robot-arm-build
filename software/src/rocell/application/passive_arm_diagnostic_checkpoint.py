"""Immutable rehearsal diagnostics, not commissioning state or replay input.

The checksum detects accidental corruption; it does not authenticate evidence.
Recovery reads one explicitly selected file and never starts a worker/device.
"""

import hashlib
import json
from pathlib import Path
import re

from .physical_onboarding_durability import (
    PublicationMode,
    publish_bytes,
    read_bounded_regular_file,
    safe_root,
    contained_path,
)
from .wizard_diagnostic_coordinator import decode_diagnostic_json

MAX_BYTES = 2 * 1024 * 1024
SCHEMA = "rocell.passive_arm_diagnostic_checkpoint.v1"
SESSION = re.compile(r"wizard-[a-f0-9]{32}\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
INTENT_SCHEMA = "rocell.passive_arm_diagnostic_intent.v1"


def encoded(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def publish(root: Path, session_id: str, retained: dict) -> dict:
    """Flush, publish without replacement, then independently reopen the bytes."""
    if not SESSION.fullmatch(session_id):
        raise ValueError("Invalid diagnostic session")
    core = dict(
        schema=SCHEMA,
        session_id=session_id,
        retained=retained,
        physical_authority=False,
        replay_allowed=False,
    )
    document = {**core, "sha256": hashlib.sha256(encoded(core)).hexdigest()}
    path = publish_bytes(
        root,
        session_id + "-passive.json",
        encoded(document),
        mode=PublicationMode.IMMUTABLE,
        maximum_bytes=MAX_BYTES,
    )
    recovered = recover(path)
    return dict(
        status="VERIFIED_DIAGNOSTIC_ONLY",
        path=str(path),
        sha256=recovered["sha256"],
        physical_authority=False,
    )


def recover(path: Path) -> dict:
    """Return detached historical bytes; no admission or current-source claims."""
    raw = read_bounded_regular_file(path, maximum_bytes=MAX_BYTES)
    value = decode_diagnostic_json(raw, maximum=MAX_BYTES)
    fields = {
        "schema",
        "session_id",
        "retained",
        "physical_authority",
        "replay_allowed",
        "sha256",
    }
    if type(value) is not dict or value.keys() != fields:
        raise ValueError("Invalid checkpoint fields")
    if (
        value["schema"] != SCHEMA
        or type(value["session_id"]) is not str
        or not SESSION.fullmatch(value["session_id"])
        or path.name != value["session_id"] + "-passive.json"
        or value["physical_authority"] is not False
        or value["replay_allowed"] is not False
    ):
        raise ValueError("Invalid checkpoint identity or authority")
    core = {key: item for key, item in value.items() if key != "sha256"}
    if (
        encoded(value) != raw
        or hashlib.sha256(encoded(core)).hexdigest() != value["sha256"]
    ):
        raise ValueError("Checkpoint checksum mismatch")
    retained = value["retained"]
    if (
        type(retained) is not dict
        or retained.keys()
        != {"operation_id", "source_sha256", "result", "physical_authority"}
        or type(retained["operation_id"]) is not str
        or re.fullmatch(r"operation-[a-f0-9]{32}", retained["operation_id"]) is None
        or type(retained["source_sha256"]) is not str
        or not SHA.fullmatch(retained["source_sha256"])
        or type(retained["result"]) is not dict
        or retained["physical_authority"] is not False
    ):
        raise ValueError("Invalid retained diagnostic")
    return {
        **value,
        "status": "HISTORICAL_DIAGNOSTIC_ONLY",
        "connected": False,
        "qualified": False,
        "authenticated": False,
    }


def publish_intent(root, session_id, request, registration, outer_payload):
    """Persist exact planned rehearsal inputs before the process can be started.

    This is diagnostic intent, not physical admission or a dispatch permit.
    Exclusive publication prevents replacing the same launch's original intent.
    """
    if type(session_id) is not str or not SESSION.fullmatch(session_id):
        raise ValueError("Invalid diagnostic session")
    from .arm_bench_qualification_contract import PassiveBenchRequest

    parsed = PassiveBenchRequest(encoded(request))
    if parsed.to_dict()["mode"] != "rehearsal" or request["launch_id"] != session_id:
        raise ValueError("Rehearsal launch binding required")
    core = dict(
        schema=INTENT_SCHEMA,
        session_id=session_id,
        request=request,
        registration=registration,
        outer_payload=outer_payload,
        physical_authority=False,
        replay_allowed=False,
    )
    record = {**core, "sha256": hashlib.sha256(encoded(core)).hexdigest()}
    path = publish_bytes(
        root,
        session_id + "-passive-intent.json",
        encoded(record),
        mode=PublicationMode.IMMUTABLE,
        maximum_bytes=MAX_BYTES,
    )
    return {"path": str(path), "record": read_intent(path)}


def read_intent(path):
    """Read historical intended inputs; hashes do not authenticate observations."""
    from .arm_bench_qualification_contract import PassiveBenchRequest

    raw = read_bounded_regular_file(path, maximum_bytes=MAX_BYTES)
    value = decode_diagnostic_json(raw, maximum=MAX_BYTES)
    if type(value) is not dict or set(value) != {
        "schema",
        "session_id",
        "request",
        "registration",
        "outer_payload",
        "physical_authority",
        "replay_allowed",
        "sha256",
    }:
        raise ValueError("Invalid passive intent fields")
    if (
        value["schema"] != INTENT_SCHEMA
        or type(value["session_id"]) is not str
        or not SESSION.fullmatch(value["session_id"])
        or path.name != value["session_id"] + "-passive-intent.json"
        or value["physical_authority"] is not False
        or value["replay_allowed"] is not False
    ):
        raise ValueError("Invalid passive intent identity")
    core = {key: item for key, item in value.items() if key != "sha256"}
    if (
        encoded(value) != raw
        or hashlib.sha256(encoded(core)).hexdigest() != value["sha256"]
    ):
        raise ValueError("Passive intent checksum mismatch")
    request = PassiveBenchRequest(encoded(value["request"])).to_dict()
    if (
        request["mode"] != "rehearsal"
        or request["launch_id"] != value["session_id"]
        or type(value["registration"]) is not dict
        or hashlib.sha256(encoded(value["registration"])).hexdigest()
        != request["references"]["runtime_sha256"]
        or type(value["outer_payload"]) is not dict
        or value["outer_payload"].get("request") != request
    ):
        raise ValueError("Passive intent request/runtime mismatch")
    return value


def recover_attempt(root, session_id):
    """Inspect exactly one named launch; never enumerate, replay or repair."""
    if type(session_id) is not str or not SESSION.fullmatch(session_id):
        raise ValueError("Invalid diagnostic session")
    root = safe_root(root)
    intent_path = contained_path(
        root, session_id + "-passive-intent.json", label="passive intent"
    )
    intent = read_intent(intent_path)
    outcome_path = contained_path(
        root, session_id + "-passive.json", label="passive outcome"
    )
    outcome = recover(outcome_path) if outcome_path.exists() else None
    status = "OUTCOME_UNKNOWN_NO_REPLAY"
    if outcome is not None:
        retained = outcome["retained"]
        steps = retained["result"].get("steps", [])
        report = steps[0].get("report", {}) if steps and type(steps[0]) is dict else {}
        matching = (
            retained["operation_id"] == intent["request"]["attempt_id"]
            and retained["source_sha256"]
            == intent["request"]["references"]["source_sha256"]
            and report.get("request") == intent["request"]
            and report.get("registration") == intent["registration"]
            and report.get("outer_payload") == intent["outer_payload"]
            and report.get("intent", {}).get("record") == intent
        )
        status = "HISTORICAL_PAIR_VERIFIED" if matching else "OUTCOME_UNBOUND_NO_REPLAY"
    return dict(
        status=status,
        intent=intent,
        outcome=outcome,
        physical_authority=False,
        connected=False,
        replay_allowed=False,
        authenticated=False,
    )
