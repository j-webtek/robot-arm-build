"""Pure passive-intake drafts, never physical evidence acceptance or attachment IO."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import json
import re
import unicodedata
from typing import Any

from .physical_camera_prerequisites import PhysicalCameraPrerequisites

SCHEMA = "rocell.physical_intake_notebook.v1"
MAX_NOTEBOOK_BYTES = 64 * 1024
MAX_REVISIONS = 128
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_DECIMAL = re.compile(r"[0-9]+(?:\.[0-9]+)?\Z")
_FALSE = (
    "physical_authority",
    "hardware_qualified",
    "canonical_stage_pass",
    "device_io_performed",
    "attachment_bytes_verified",
)
_MEANING = (
    "Unaccepted passive-intake draft. Operator text and evidence notes are not "
    "verified measurements or attachments; no canonical stage, hazard, epoch, "
    "device connection or physical qualification is accepted. INT-005 flatness "
    "acceptance remains deferred until the target accuracy budget is closed."
)
_ERRORS = {
    "INVALID_NOTEBOOK": "The draft notebook is malformed or differs from its bound original requirements.",
    "INVALID_PREREQUISITES": "Exact retained camera prerequisites are required; this notebook cannot qualify them.",
    "INVALID_INPUT": "Use nonempty bounded text without control characters or surrounding whitespace.",
    "INVALID_OBSERVATION": "Choose OBSERVED or UNKNOWN; an UNKNOWN value must describe why it is unknown.",
    "INVALID_DECIMAL": "Enter a positive plain decimal in the original unit; only INT-005 flatness permits zero.",
    "UNKNOWN_RECORD": "Choose one of the sixteen original camera-receipt questions.",
    "REVISION_LIMIT": "The draft reached its 128-revision limit; retain/export its original history.",
    "HASH_MISMATCH": "The draft differs from the independently retained snapshot hash.",
    "BYTE_LIMIT": "The complete draft exceeds its 64 KiB byte budget; no entry was truncated.",
}


class PhysicalIntakeNotebookError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(_ERRORS[code])


def _require(condition: bool, code: str = "INVALID_NOTEBOOK") -> None:
    if not condition:
        raise PhysicalIntakeNotebookError(code)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        _require(key not in result)
        result[key] = value
    return result


def _text(value: Any, maximum: int) -> None:
    _require(
        type(value) is str and bool(value) and value.strip() == value, "INVALID_INPUT"
    )
    _require(
        not any(unicodedata.category(char).startswith("C") for char in value),
        "INVALID_INPUT",
    )
    _require(len(value.encode("utf-8")) <= maximum, "INVALID_INPUT")


def _questions(prerequisites: PhysicalCameraPrerequisites) -> list[dict[str, Any]]:
    _require(
        type(prerequisites) is PhysicalCameraPrerequisites, "INVALID_PREREQUISITES"
    )
    original = PhysicalCameraPrerequisites(prerequisites.payload).to_dict()
    stages = [
        row
        for row in original["requirements"]["stages"]
        if row["stage"] == "camera_receipt"
    ]
    _require(
        len(stages) == 1 and len(stages[0]["intake_rows"]) == 16,
        "INVALID_PREREQUISITES",
    )
    return stages[0]["intake_rows"]


def _observation(value: Any, question: dict[str, Any]) -> None:
    _require(
        type(value) is dict
        and set(value)
        == {
            "status",
            "observed_value",
            "method",
            "evidence_note",
            "operator_id",
            "recorded_at_ns",
        }
    )
    _require(
        type(value["status"]) is str and value["status"] in {"OBSERVED", "UNKNOWN"},
        "INVALID_OBSERVATION",
    )
    for name, maximum in (
        ("observed_value", 256),
        ("method", 512),
        ("evidence_note", 1024),
        ("operator_id", 64),
    ):
        _text(value[name], maximum)
    _require(
        type(value["recorded_at_ns"]) is int and 0 < value["recorded_at_ns"] < 2**63,
        "INVALID_INPUT",
    )
    if value["status"] == "OBSERVED" and question["unit"] in {"mm", "g"}:
        raw = value["observed_value"]
        _require(_DECIMAL.fullmatch(raw) is not None, "INVALID_DECIMAL")
        number = Decimal(raw)
        _require(
            number.is_finite()
            and (number >= 0 if question["record_id"] == "INT-005" else number > 0),
            "INVALID_DECIMAL",
        )


def _coverage(rows: list[dict[str, Any]]) -> dict[str, int]:
    observed = sum(
        row["observation"] is not None and row["observation"]["status"] == "OBSERVED"
        for row in rows
    )
    unknown = sum(
        row["observation"] is not None and row["observation"]["status"] == "UNKNOWN"
        for row in rows
    )
    return {
        "total": 16,
        "observed": observed,
        "unknown": unknown,
        "unrecorded": 16 - observed - unknown,
    }


@dataclass(frozen=True, slots=True)
class PhysicalIntakeNotebook:
    payload: bytes
    _prerequisites: PhysicalCameraPrerequisites = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        try:
            self._validate()
        except PhysicalIntakeNotebookError:
            raise
        except (TypeError, ValueError, KeyError, RecursionError, UnicodeError) as error:
            raise PhysicalIntakeNotebookError("INVALID_NOTEBOOK") from error

    def _validate(self) -> None:
        _require(type(self.payload) is bytes)
        _require(0 < len(self.payload) <= MAX_NOTEBOOK_BYTES, "BYTE_LIMIT")
        value = json.loads(self.payload.decode("ascii"), object_pairs_hook=_pairs)
        _require(
            type(value) is dict
            and set(value)
            == {
                "schema",
                "binding",
                "revision",
                "previous_sha256",
                "rows",
                "coverage",
                "meaning",
                *_FALSE,
            }
        )
        _require(
            _canonical(value) == self.payload
            and value["schema"] == SCHEMA
            and value["meaning"] == _MEANING
        )
        _require(all(value[name] is False for name in _FALSE))
        questions = _questions(self._prerequisites)
        original = self._prerequisites.to_dict()["binding"]
        binding = value["binding"]
        _require(
            type(binding) is dict
            and set(binding)
            == {
                "source_sha256",
                "session_id",
                "origin_launch_id",
                "launch_session_id",
                "prerequisites_sha256",
            }
        )
        _require(
            binding["source_sha256"] == original["source_sha256"]
            and binding["session_id"] == original["session_id"]
            and binding["origin_launch_id"] == original["launch_session_id"]
            and binding["prerequisites_sha256"] == self._prerequisites.evidence_sha256
            and type(binding["launch_session_id"]) is str
            and _ID.fullmatch(binding["launch_session_id"]) is not None
        )
        revision = value["revision"]
        _require(type(revision) is int and 0 <= revision <= MAX_REVISIONS)
        previous = value["previous_sha256"]
        _require(
            previous is None
            if revision == 0
            else (
                type(previous) is str
                and _HASH.fullmatch(previous) is not None
                and previous != "0" * 64
            )
        )
        rows = value["rows"]
        _require(type(rows) is list and len(rows) == 16)
        for row, question in zip(rows, questions):
            _require(type(row) is dict and set(row) == set(question))
            _require(_canonical({**row, "observation": None}) == _canonical(question))
            if row["observation"] is not None:
                _observation(row["observation"], question)
        coverage = _coverage(rows)
        _require(_canonical(value["coverage"]) == _canonical(coverage))
        written = coverage["observed"] + coverage["unknown"]
        _require(written == 0 if revision == 0 else 1 <= written <= revision)

    @classmethod
    def start(
        cls, prerequisites: PhysicalCameraPrerequisites, *, launch_session_id: str
    ) -> "PhysicalIntakeNotebook":
        rows = _questions(prerequisites)
        _require(
            type(launch_session_id) is str
            and _ID.fullmatch(launch_session_id) is not None,
            "INVALID_INPUT",
        )
        original = prerequisites.to_dict()["binding"]
        return cls(
            _canonical(
                {
                    "schema": SCHEMA,
                    "binding": {
                        "source_sha256": original["source_sha256"],
                        "session_id": original["session_id"],
                        "origin_launch_id": original["launch_session_id"],
                        "launch_session_id": launch_session_id,
                        "prerequisites_sha256": prerequisites.evidence_sha256,
                    },
                    "revision": 0,
                    "previous_sha256": None,
                    "rows": rows,
                    "coverage": _coverage(rows),
                    **{name: False for name in _FALSE},
                    "meaning": _MEANING,
                }
            ),
            prerequisites,
        )

    @classmethod
    def from_payload(
        cls,
        payload: bytes,
        *,
        prerequisites: PhysicalCameraPrerequisites,
        expected_sha256: str,
    ) -> "PhysicalIntakeNotebook":
        _require(
            type(payload) is bytes
            and type(expected_sha256) is str
            and _HASH.fullmatch(expected_sha256) is not None
            and hashlib.sha256(payload).hexdigest() == expected_sha256,
            "HASH_MISMATCH",
        )
        return cls(payload, prerequisites)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.payload)

    def view(self) -> dict[str, Any]:
        return {**self.to_dict(), "snapshot_sha256": self.sha256}

    def choices(self) -> list[dict[str, str]]:
        return [
            {
                "value": row["record_id"],
                "label": row["record_id"]
                + " — "
                + row["measurement"]
                + " ("
                + row["unit"]
                + ")",
            }
            for row in self.to_dict()["rows"]
        ]

    def record(
        self,
        *,
        record_id: str,
        observation_status: str,
        observed_value: str,
        method: str,
        evidence_note: str,
        operator_id: str,
        recorded_at_ns: int,
    ) -> "PhysicalIntakeNotebook":
        value = self.to_dict()
        _require(value["revision"] < MAX_REVISIONS, "REVISION_LIMIT")
        rows = [row for row in value["rows"] if row["record_id"] == record_id]
        _require(type(record_id) is str and len(rows) == 1, "UNKNOWN_RECORD")
        observation = {
            "status": observation_status,
            "observed_value": observed_value,
            "method": method,
            "evidence_note": evidence_note,
            "operator_id": operator_id,
            "recorded_at_ns": recorded_at_ns,
        }
        _observation(observation, rows[0])
        rows[0]["observation"] = observation
        value.update(
            revision=value["revision"] + 1,
            previous_sha256=self.sha256,
            coverage=_coverage(value["rows"]),
        )
        return type(self)(_canonical(value), self._prerequisites)

    def revise_for_launch(self, *, launch_session_id: str) -> "PhysicalIntakeNotebook":
        """Explicitly derive a draft; copied observations keep their old actors/times.

        The received-stage service additionally binds this original notebook's
        hash in its submission. This is not a fresh measurement or a relabeling
        of the prior notebook's original-store reference.
        """
        value = self.to_dict()
        _require(value["revision"] < MAX_REVISIONS, "REVISION_LIMIT")
        _require(
            type(launch_session_id) is str
            and _ID.fullmatch(launch_session_id) is not None,
            "INVALID_INPUT",
        )
        if value["revision"] == 0:
            # A blank notebook has no observation revision to carry forward.
            # The received submission separately records its exact origin hash.
            return type(self).start(
                self._prerequisites, launch_session_id=launch_session_id
            )
        value["binding"]["launch_session_id"] = launch_session_id
        value.update(revision=value["revision"] + 1, previous_sha256=self.sha256)
        return type(self)(_canonical(value), self._prerequisites)
