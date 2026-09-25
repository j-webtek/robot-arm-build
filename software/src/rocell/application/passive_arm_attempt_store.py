"""One-use engineering-attempt journal, separate from rehearsal checkpoints.

Store exact entry originals and preserve raw outcomes before interpreting them.
This is persistence machinery, not an authenticator or native dispatch permit.
Only a future registered service composition may supply authenticated originals
and use the live consume receipt. Recovery is diagnostic-only and never resumes.
"""

import base64
import hashlib
from pathlib import Path
import re
from threading import Lock

from .arm_bench_qualification_contract import PassiveBenchRequest, _canonical
from .passive_arm_entry_policy import PassiveEntryEvidence
from .physical_onboarding_durability import (
    PublicationMode,
    publish_bytes,
    publish_reservation_bytes,
    read_bounded_regular_file,
    safe_root,
    contained_path,
)
from .wizard_diagnostic_coordinator import decode_diagnostic_json


MAX_BYTES = 1024 * 1024
# Match the supervised native child's complete output budgets. Base64 encoding
# both streams still fits comfortably inside the one-MiB journal record bound.
MAX_STDOUT_BYTES = 256 * 1024
MAX_STDERR_BYTES = 8192
STAGES = frozenset({"prepared", "consumed", "claimed", "outcome"})


def _path(root, attempt_id, stage):
    if (
        type(attempt_id) is not str
        or re.fullmatch(r"operation-[a-f0-9]{32}", attempt_id) is None
        or stage not in STAGES
    ):
        raise ValueError("Exact service attempt and journal stage required")
    return contained_path(
        safe_root(Path(root)),
        attempt_id + "-physical-passive-" + stage + ".json",
        label="passive attempt",
    )


def _publish(root, attempt_id, stage, core):
    path = _path(root, attempt_id, stage)
    record = {
        "schema": "rocell.physical_passive_attempt_journal.v1",
        "attempt_id": attempt_id,
        "stage": stage,
        "body": core,
        "replay_allowed": False,
        "physical_authority": False,
    }
    raw = _canonical(record)
    if stage == "claimed":
        # The claim consumes its final name before writing. An incomplete tail
        # intentionally blocks all subsequent claim attempts, including restart.
        publish_reservation_bytes(Path(root), path.name, raw, maximum_bytes=MAX_BYTES)
    else:
        publish_bytes(
            Path(root),
            path.name,
            raw,
            mode=PublicationMode.IMMUTABLE,
            maximum_bytes=MAX_BYTES,
        )
    if read_bounded_regular_file(path, maximum_bytes=MAX_BYTES) != raw:
        raise ValueError("Published attempt readback mismatch")
    return hashlib.sha256(raw).hexdigest()


class PassiveAttemptJournal:
    """Live one-use journal; no reload constructor and no worker callback.

    Any consume failure burns this instance, including uncertain publication.
    Immutable filenames also prevent another instance overwriting the attempt.
    A receipt must never be treated as a permit outside the live service owner.
    """

    def __init__(
        self, root, request, evidence, originals, registration, *, now_monotonic_ns
    ):
        if (
            type(request) is not PassiveBenchRequest
            or type(evidence) is not PassiveEntryEvidence
        ):
            raise ValueError("Exact passive request and entry evidence required")
        assessment = evidence.assess(
            request, originals, now_monotonic_ns=now_monotonic_ns
        )
        if assessment["blockers"]:
            raise ValueError("Passive entry association held")
        request.require_time_available(now_monotonic_ns)
        self._root = safe_root(Path(root))
        self._request = PassiveBenchRequest(request.payload)
        self._evidence = PassiveEntryEvidence(evidence.payload)
        self._originals = dict(originals)
        body = request.to_dict()
        self._attempt = body["attempt_id"]
        # This associates registration bytes; the supervisor must independently
        # validate the closed worker registration before creating this journal.
        registration_raw = _canonical(registration)
        if (
            type(registration) is not dict
            or len(registration_raw) > 65536
            or hashlib.sha256(registration_raw).hexdigest()
            != body["references"]["runtime_sha256"]
        ):
            raise ValueError("Runtime registration mismatch")
        self._lock = Lock()
        self._consumed = False
        self._outcome_attempted = False
        self._consumption_sha256 = None
        self._prepared_sha256 = _publish(
            self._root,
            self._attempt,
            "prepared",
            {
                "request": body,
                "entry_evidence_base64": base64.b64encode(evidence.payload).decode(
                    "ascii"
                ),
                "originals_base64": {
                    key: base64.b64encode(raw).decode("ascii")
                    for key, raw in originals.items()
                },
                "registration": registration,
                "references_authenticated_by_journal": False,
            },
        )

    def consume(self, *, now_monotonic_ns):
        """Durably burn one attempt before dispatch; do not retry on failure."""
        with self._lock:
            if self._consumed:
                raise ValueError("Passive attempt already consumed")
            self._consumed = True
            assessment = self._evidence.assess(
                self._request, self._originals, now_monotonic_ns=now_monotonic_ns
            )
            if assessment["blockers"]:
                raise ValueError("Passive setup expired or changed")
            self._request.require_time_available(now_monotonic_ns)
            raw = read_bounded_regular_file(
                _path(self._root, self._attempt, "prepared"), maximum_bytes=MAX_BYTES
            )
            if hashlib.sha256(raw).hexdigest() != self._prepared_sha256:
                raise ValueError("Prepared original changed")
            self._consumption_sha256 = _publish(
                self._root,
                self._attempt,
                "consumed",
                {
                    "prepared_sha256": self._prepared_sha256,
                    "consumed_monotonic_ns": now_monotonic_ns,
                    "request_sha256": self._request.request_sha256,
                    "dispatch_may_have_started": True,
                },
            )
            return {
                "attempt_id": self._attempt,
                "consumption_sha256": self._consumption_sha256,
                "replay_allowed": False,
                "physical_authority": False,
            }

    def retain_outcome(self, *, stdout: bytes, stderr: bytes, process_status: str):
        """Retain malformed/failed child output too, without claiming cleanup."""
        with self._lock:
            if self._consumption_sha256 is None or self._outcome_attempted:
                raise ValueError(
                    "Consumed attempt and first outcome publication required"
                )
            self._outcome_attempted = True
            if (
                type(stdout) is not bytes
                or len(stdout) > MAX_STDOUT_BYTES
                or type(stderr) is not bytes
                or len(stderr) > MAX_STDERR_BYTES
            ):
                raise ValueError("Bounded raw process output required")
            if process_status not in {
                "SUCCEEDED",
                "FAILED",
                "TIMED_OUT",
                "CANCELLED",
                "UNKNOWN",
            }:
                raise ValueError("Closed process outcome required")
            return _publish(
                self._root,
                self._attempt,
                "outcome",
                {
                    "consumption_sha256": self._consumption_sha256,
                    "process_status": process_status,
                    "stdout_base64": base64.b64encode(stdout).decode("ascii"),
                    "stderr_base64": base64.b64encode(stderr).decode("ascii"),
                    "device_cleanup": "NOT_ESTABLISHED_BY_PROCESS_STATUS",
                },
            )


def inspect_attempt(root, attempt_id):
    """Read only exact journal names. Missing outcome is unknown, never success."""
    records, hashes = {}, {}
    for stage in ("prepared", "consumed", "claimed", "outcome"):
        path = _path(root, attempt_id, stage)
        try:
            path.lstat()
        except FileNotFoundError:
            records[stage] = None
            continue
        raw = read_bounded_regular_file(path, maximum_bytes=MAX_BYTES)
        record = decode_diagnostic_json(raw, maximum=MAX_BYTES)
        if (
            type(record) is not dict
            or set(record)
            != {
                "schema",
                "attempt_id",
                "stage",
                "body",
                "replay_allowed",
                "physical_authority",
            }
            or record["schema"] != "rocell.physical_passive_attempt_journal.v1"
            or record["attempt_id"] != attempt_id
            or record["stage"] != stage
            or record["replay_allowed"] is not False
            or record["physical_authority"] is not False
            or type(record["body"]) is not dict
            or _canonical(record) != raw
        ):
            raise ValueError("Invalid retained attempt record")
        hashes[stage] = hashlib.sha256(raw).hexdigest()
        records[stage] = record
    status = "NO_ATTEMPT"
    if records["prepared"] is not None:
        status = "PREPARED_NOT_REPLAYABLE"
    if records["consumed"] is not None:
        status = "OUTCOME_UNKNOWN_NO_REPLAY"
        if records["prepared"] is None or records["consumed"]["body"].get(
            "prepared_sha256"
        ) != hashes.get("prepared"):
            raise ValueError("Unbound consumption record")
    if records["claimed"] is not None:
        if records["consumed"] is None or records["claimed"]["body"].get(
            "consumption_sha256"
        ) != hashes.get("consumed"):
            raise ValueError("Unbound child claim")
    if records["outcome"] is not None:
        if records["consumed"] is None or records["outcome"]["body"].get(
            "consumption_sha256"
        ) != hashes.get("consumed"):
            raise ValueError("Unbound outcome record")
        status = "OUTCOME_RETAINED_NOT_DEVICE_ACCEPTANCE"
    return {
        "status": status,
        "records": records,
        "replay_allowed": False,
        "physical_authority": False,
        "authenticated": False,
    }
