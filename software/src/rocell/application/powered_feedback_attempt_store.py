"""Durable one-use powered-feedback attempts; storage is not a dispatch permit.

The future supervised coordinator must independently admit firmware/runtime and
own the native child. This journal only preserves associated originals, burns an
attempt before dispatch, and retains raw process outcomes without interpreting
them as device cleanup or a successful connection. Recovery never resumes I/O.
"""

import base64
import hashlib
from pathlib import Path
import re
from threading import Lock

from .arm_bench_qualification_contract import _canonical
from .powered_arm_feedback_preparation import (
    PreparedPoweredFeedback,
    prepare_powered_feedback,
)
from .physical_onboarding_durability import (
    PublicationMode,
    contained_path,
    publish_bytes,
    publish_reservation_bytes,
    read_bounded_regular_file,
    safe_root,
)
from .wizard_diagnostic_coordinator import decode_diagnostic_json

MAX_RECORD_BYTES = 1024 * 1024
MAX_STDOUT_BYTES = 256 * 1024
MAX_STDERR_BYTES = 8192
STAGES = ("prepared", "consumed", "claimed", "outcome")


def attempt_path(root, attempt_id, stage):
    if (
        type(attempt_id) is not str
        or re.fullmatch(r"operation-[a-f0-9]{32}", attempt_id) is None
        or type(stage) is not str
        or stage not in STAGES
    ):
        raise ValueError("Exact powered attempt ID and stage required")
    return contained_path(
        safe_root(Path(root)),
        attempt_id + "-powered-feedback-" + stage + ".json",
        label="powered feedback attempt",
    )


def _publish(root, attempt_id, stage, body):
    path = attempt_path(root, attempt_id, stage)
    raw = _canonical(
        {
            "schema": "rocell.powered_feedback_attempt_journal.v1",
            "attempt_id": attempt_id,
            "stage": stage,
            "body": body,
            "replay_allowed": False,
            "physical_authority": False,
        }
    )
    if stage in {"consumed", "claimed"}:
        # Occupy the final name before any bytes are written. A partial record
        # intentionally prevents retry following a crash or uncertain write.
        publish_reservation_bytes(
            Path(root), path.name, raw, maximum_bytes=MAX_RECORD_BYTES
        )
    else:
        publish_bytes(
            Path(root),
            path.name,
            raw,
            mode=PublicationMode.IMMUTABLE,
            maximum_bytes=MAX_RECORD_BYTES,
        )
    if read_bounded_regular_file(path, maximum_bytes=MAX_RECORD_BYTES) != raw:
        raise ValueError("Powered attempt publication readback mismatch")
    return hashlib.sha256(raw).hexdigest()


class PoweredFeedbackAttemptJournal:
    """No reload constructor or native callback; each instance is one-use."""

    def __init__(
        self,
        root,
        prepared,
        *,
        startup_operation_id,
        current_source_sha256,
        now_monotonic_ns
    ):
        if type(prepared) is not PreparedPoweredFeedback:
            raise ValueError("Exact associated powered originals required")
        self._root = safe_root(Path(root))
        self._prepared = prepared
        self._startup_operation_id = startup_operation_id
        self._revalidate(current_source_sha256, now_monotonic_ns)
        self._attempt_id = prepared.intent.to_dict()["attempt_id"]
        self._lock = Lock()
        self._consumed = False
        self._outcome_attempted = False
        self._consumption_sha256 = None
        self._prepared_sha256 = _publish(
            self._root,
            self._attempt_id,
            "prepared",
            {
                "intent": prepared.intent.to_dict(),
                "startup_operation_id": startup_operation_id,
                "originals_base64": {
                    name: base64.b64encode(raw).decode("ascii")
                    for name, raw in prepared.originals
                },
                "references_authenticated_by_journal": False,
            },
        )

    def _revalidate(self, source_sha256, now_monotonic_ns):
        # Do not trust construction of the dataclass as evidence admission.
        # Reopen startup and reconstruct the full metadata/review association.
        originals = dict(self._prepared.originals)
        rebuilt = prepare_powered_feedback(
            intent=self._prepared.intent,
            root=self._root,
            startup_operation_id=self._startup_operation_id,
            current_source_sha256=source_sha256,
            native_original=originals["native_identity_original_sha256"],
            generic_review=decode_diagnostic_json(
                originals["generic_review_original"], maximum=262144
            ),
            runtime_original=originals["runtime_sha256"],
            serial_profile_original=originals["serial_profile_sha256"],
            protocol_review_original=originals["protocol_review_sha256"],
            firmware_review_original=originals["firmware_compatibility_review_sha256"],
            now_monotonic_ns=now_monotonic_ns,
        )
        if rebuilt != self._prepared:
            raise ValueError("Powered original association changed")

    def consume(self, *, current_source_sha256, now_monotonic_ns):
        with self._lock:
            if self._consumed:
                raise ValueError("Powered attempt already consumed")
            self._consumed = True  # Any failure burns this live instance.
            self._revalidate(current_source_sha256, now_monotonic_ns)
            raw = read_bounded_regular_file(
                attempt_path(self._root, self._attempt_id, "prepared"),
                maximum_bytes=MAX_RECORD_BYTES,
            )
            if hashlib.sha256(raw).hexdigest() != self._prepared_sha256:
                raise ValueError("Prepared powered record changed")
            self._consumption_sha256 = _publish(
                self._root,
                self._attempt_id,
                "consumed",
                {
                    "prepared_sha256": self._prepared_sha256,
                    "request_sha256": self._prepared.intent.request_sha256,
                    "consumed_monotonic_ns": now_monotonic_ns,
                    "dispatch_may_have_started": True,
                },
            )
            return {
                "attempt_id": self._attempt_id,
                "consumption_sha256": self._consumption_sha256,
                "physical_authority": False,
                "replay_allowed": False,
            }

    def retain_outcome(self, *, stdout, stderr, process_status):
        with self._lock:
            if self._consumption_sha256 is None or self._outcome_attempted:
                raise ValueError("First outcome of a consumed powered attempt required")
            self._outcome_attempted = True
            if (
                type(stdout) is not bytes
                or len(stdout) > MAX_STDOUT_BYTES
                or type(stderr) is not bytes
                or len(stderr) > MAX_STDERR_BYTES
                or type(process_status) is not str
                or process_status
                not in {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED", "UNKNOWN"}
            ):
                raise ValueError(
                    "Bounded raw process output and closed status required"
                )
            return _publish(
                self._root,
                self._attempt_id,
                "outcome",
                {
                    "consumption_sha256": self._consumption_sha256,
                    "process_status": process_status,
                    "stdout_base64": base64.b64encode(stdout).decode("ascii"),
                    "stderr_base64": base64.b64encode(stderr).decode("ascii"),
                    "device_cleanup": "NOT_ESTABLISHED_BY_PROCESS_STATUS",
                },
            )


def collect_attempt(root, attempt_id):
    """Preserve partial/malformed records as historical bytes, never replay them.

    This intentionally does not claim chain verification, authentication, device
    cleanup or successful execution. A partial consumed file is evidence of an
    unknown attempt, not permission to dispatch again.
    """
    records = []
    for stage in STAGES:
        path = attempt_path(root, attempt_id, stage)
        try:
            # The bounded reader wraps OS errors; establish absence explicitly.
            # A subsequent race is still an unreadable/uncertain snapshot.
            path.lstat()
        except FileNotFoundError:
            records.append({"stage": stage, "status": "MISSING"})
            continue
        except OSError as error:
            records.append(
                {
                    "stage": stage,
                    "status": "UNREADABLE",
                    "error_type": type(error).__name__,
                }
            )
            continue
        try:
            raw = read_bounded_regular_file(path, maximum_bytes=MAX_RECORD_BYTES)
        except FileNotFoundError:
            records.append({"stage": stage, "status": "MISSING"})
        except Exception as error:
            records.append(
                {
                    "stage": stage,
                    "status": "UNREADABLE",
                    "error_type": type(error).__name__,
                }
            )
        else:
            records.append(
                {
                    "stage": stage,
                    "status": "BYTES_RETAINED",
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "base64_chunks": [
                        base64.b64encode(raw[i : i + 32768]).decode("ascii")
                        for i in range(0, len(raw), 32768)
                    ],
                }
            )
    return {
        "schema": "rocell.powered_feedback_attempt_export.v1",
        "attempt_id": attempt_id,
        "records": records,
        "historical_only": True,
        "atomic_snapshot": False,
        "chain_verified": False,
        "replay_allowed": False,
        "physical_authority": False,
    }
