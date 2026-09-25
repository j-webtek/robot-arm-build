"""Bounded observations of an existing owner; unavailable never means false/zero.

Reading an owner's attributes neither launches nor authorizes it. This records
what was available at one boundary, not an atomic kernel snapshot or proof that
a device operation happened. The supervisor must retain before/after cleanup
snapshots and keep uncertain owners alive separately.
"""

import base64
from dataclasses import dataclass
from typing import Any

from .native_camera_protocol import canonical, digest, _require
from .owned_worker_process import WorkerProcessBudget, decode_owned_json

SCHEMA = "rocell.native_camera_activation_owner_observation.v1"
MAX_BYTES = 448 * 1024
BOOL_FIELDS = (
    "created",
    "resumed",
    "tree_exited",
    "stdout_eof",
    "stderr_eof",
    "pending",
)
INT_FIELDS = (
    "pid",
    "written",
    "peak_handles",
    "peak_processes",
    "handles_remaining",
    "unclosed_handles_remaining",
    "pins_remaining",
)
FIELDS = tuple(sorted((*BOOL_FIELDS, *INT_FIELDS, "returncode", "stdout", "stderr")))
REASONS = {"ATTRIBUTE_UNAVAILABLE", "INVALID_VALUE", "OWNER_NOT_CONSTRUCTED"}


def _value_valid(name: str, value: Any) -> bool:
    if name in BOOL_FIELDS:
        return type(value) is bool
    if name == "returncode":
        return value is None or type(value) is int and -(2**31) <= value < 2**32
    if name in INT_FIELDS:
        return type(value) is int and 0 <= value < 2**63
    return type(value) is bytes


def _wire(value: bytes, maximum: int) -> dict[str, Any]:
    retained = value[:maximum]
    return dict(
        base64=base64.b64encode(retained).decode("ascii"),
        retained_bytes=len(retained),
        retained_sha256=digest(retained),
        omitted_from_observed_buffer=len(value) - len(retained),
    )


def read_buffer(data: Any, maximum: int) -> bytes:
    _require(
        type(data) is dict
        and set(data)
        == {
            "base64",
            "retained_bytes",
            "retained_sha256",
            "omitted_from_observed_buffer",
        },
        "ACTIVATION_BUFFER_FIELDS",
    )
    _require(
        type(data["base64"]) is str and len(data["base64"]) <= 4 * ((maximum + 2) // 3),
        "ACTIVATION_BUFFER_LIMIT",
    )
    try:
        value = base64.b64decode(data["base64"], validate=True)
    except Exception as error:
        raise ValueError("ACTIVATION_BUFFER_BASE64") from error
    _require(
        type(data["retained_bytes"]) is int
        and 0 <= data["retained_bytes"] <= maximum
        and len(value) == data["retained_bytes"]
        and digest(value) == data["retained_sha256"]
        and base64.b64encode(value).decode("ascii") == data["base64"],
        "ACTIVATION_BUFFER_HASH",
    )
    omitted = data["omitted_from_observed_buffer"]
    _require(
        type(omitted) is int
        and 0 <= omitted < 2**63
        and (omitted == 0 or len(value) == maximum),
        "ACTIVATION_BUFFER_OMISSION",
    )
    return value


@dataclass(frozen=True, slots=True)
class ActivationOwnerObservation:
    payload: bytes

    def __post_init__(self) -> None:
        self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        data = decode_owned_json(self.payload, maximum=MAX_BYTES)
        _require(
            canonical(data) == self.payload
            and set(data) == {"schema", "fields", "stdout_limit", "stderr_limit"}
            and data["schema"] == SCHEMA,
            "ACTIVATION_OBSERVATION_SCHEMA",
        )
        _require(
            type(data["fields"]) is dict and set(data["fields"]) == set(FIELDS),
            "ACTIVATION_OBSERVATION_FIELDS",
        )
        for name, maximum in (("stdout", 256 * 1024), ("stderr", 64 * 1024)):
            limit = data[name + "_limit"]
            _require(
                type(limit) is int and 128 <= limit <= maximum,
                "ACTIVATION_OBSERVATION_PIPE_LIMIT",
            )
        for name, field in data["fields"].items():
            _require(
                type(field) is dict
                and set(field) == {"available", "value", "reason"}
                and type(field["available"]) is bool,
                "ACTIVATION_OBSERVATION_AVAILABILITY",
            )
            if not field["available"]:
                _require(
                    field["value"] is None
                    and type(field["reason"]) is str
                    and field["reason"] in REASONS,
                    "ACTIVATION_OBSERVATION_UNKNOWN",
                )
            else:
                _require(
                    field["reason"] is None, "ACTIVATION_OBSERVATION_AVAILABLE_REASON"
                )
                value = (
                    read_buffer(field["value"], data[name + "_limit"])
                    if name in ("stdout", "stderr")
                    else field["value"]
                )
                _require(_value_valid(name, value), "ACTIVATION_OBSERVATION_VALUE")
        return data

    def values(self) -> dict[str, Any]:
        """Only available values are included; a known pending exit may be None."""
        data = self.to_dict()
        return {
            name: (
                read_buffer(field["value"], data[name + "_limit"])
                if name in ("stdout", "stderr")
                else field["value"]
            )
            for name, field in data["fields"].items()
            if field["available"]
        }

    @property
    def unavailable_fields(self) -> tuple[str, ...]:
        return tuple(
            name
            for name, field in self.to_dict()["fields"].items()
            if not field["available"]
        )


def capture_activation_owner(
    owner: Any | None, budget: WorkerProcessBudget
) -> ActivationOwnerObservation:
    """Read the supplied owner once per field; do not invent failed attribute reads.

    Pipe omission counts here refer ONLY to the observed in-memory buffer. They
    do not estimate bytes the process owner/driver failed to deliver or retain.
    """
    _require(type(budget) is WorkerProcessBudget, "ACTIVATION_OBSERVATION_BUDGET")
    budget.__post_init__()
    result = {}
    for name in FIELDS:
        reason = None
        value: Any = None
        if owner is None:
            reason = "OWNER_NOT_CONSTRUCTED"
        else:
            try:
                if name.endswith("_remaining"):
                    value = len(getattr(owner, name[:-10]))
                else:
                    value = getattr(owner, name)
                if not _value_valid(name, value):
                    reason = "INVALID_VALUE"
            except Exception:
                reason = "ATTRIBUTE_UNAVAILABLE"
        if reason is None and name in ("stdout", "stderr"):
            value = _wire(value, getattr(budget, name + "_bytes"))
        result[name] = dict(
            available=reason is None,
            value=value if reason is None else None,
            reason=reason,
        )
    return ActivationOwnerObservation(
        canonical(
            dict(
                schema=SCHEMA,
                fields=result,
                stdout_limit=budget.stdout_bytes,
                stderr_limit=budget.stderr_bytes,
            )
        )
    )
