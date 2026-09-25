"""Small camera-entry display contract; no original authentication or I/O."""

from copy import deepcopy
import re

from .physical_camera_mode_entry import FALSE_FIELDS

SCHEMA = "rocell.wizard_camera_mode_entry.v1"
ACTION = "physical_camera_mode_enter"
MEANING = (
    "Setup entry only, not a camera connection. Probe, settings, images, arm "
    "startup and movement require separate later steps. Partial entries are "
    "diagnostic-only and are not automatically retried."
)
RETENTION = (
    "COLLECTED_NOT_M1_RETAINED",
    "M1_PUBLICATION_UNCONFIRMED",
    "M1_PUBLISHED_READBACK_PENDING",
    "M1_FULL_BYTES_READ_BACK",
)
ENTRY_FIELDS = (
    "entry_id",
    "entry_sha256",
    "state",
    "session_id",
    "cell_id",
    "origin_launch_id",
    "entry_launch_id",
    "header_sha256",
    "selected_identity_sha256",
    "complete_review_sha256",
    "operator_id",
)
ATTEMPT_FIELDS = ("entry_id", "entry_sha256", "retention", "event_count")
FIELDS = (
    "schema",
    "source_sha256",
    "launch_session_id",
    "publication",
    "status",
    "entry",
    "attempt",
    "attempted",
    "next_action",
    "meaning",
    *sorted(FALSE_FIELDS),
)


def project_mode_entry(setup, workflow, *, attempted, attempt, available):
    """Summarize the owner's cache only. Pending publication withholds subjects."""
    publication = deepcopy(setup["publication"])
    original = (workflow or {}).get("camera_mode_entry")
    entry = None
    if original is not None:
        record = original["entry"]
        document = record["document"]
        binding = document["binding"]
        entry = dict(
            entry_id=document["entry_id"],
            entry_sha256=record["evidence_sha256"],
            state=original["state"],
            operator_id=document["operator_id"],
            **{key: binding[key] for key in ENTRY_FIELDS if key in binding},
        )
    summary = (
        None
        if attempt is None
        else dict(
            entry_id=attempt["entry_id"],
            entry_sha256=attempt["record"]["evidence_sha256"],
            retention=attempt["record"]["retention"],
            event_count=len(attempt["events"]),
        )
    )
    if publication["status"] == "PENDING":
        status, entry, summary = "PENDING_PUBLICATION", None, None
    elif publication["status"] == "CURRENT" and entry is not None:
        status = "ENTERED" if entry["state"] == "ENTERED" else "INCOMPLETE_HELD"
        if (
            status == "ENTERED"
            and (workflow.get("camera_probe_preparation") or {}).get("state")
            == "PREPARED_REVIEW_REQUIRED"
        ):
            status = "ENTERED_PREPARATION_PENDING_REVIEW"
    elif available:
        status = "READY_TO_ENTER"
    elif entry is not None or attempted or summary is not None:
        status = "HISTORICAL_HELD"
    else:
        status = "NOT_STARTED"
    return dict(
        schema=SCHEMA,
        source_sha256=setup["source_sha256"],
        launch_session_id=setup["launch_session_id"],
        publication=publication,
        status=status,
        entry=entry,
        attempt=summary,
        attempted=attempted,
        next_action=ACTION if status == "READY_TO_ENTER" else None,
        meaning=MEANING,
        **{flag: False for flag in FALSE_FIELDS},
    )


def _exact(value, keys):
    return type(value) is dict and set(value) == set(keys)


def _match(value, pattern):
    return type(value) is str and re.fullmatch(pattern, value) is not None


def mode_entry_projection_valid(value, setup) -> bool:
    """Display consistency on already validated Setup, never action admission."""
    try:
        return _valid(value, setup)
    except (
        KeyError,
        TypeError,
        ValueError,
        AttributeError,
        IndexError,
        RecursionError,
    ):
        return False


def _valid(value, setup):
    if not (
        _exact(value, FIELDS)
        and value["schema"] == SCHEMA
        and _match(value["source_sha256"], r"[0-9a-f]{64}")
        and _match(value["launch_session_id"], r"wizard-[0-9a-f]{32}")
        and value["source_sha256"] == setup["source_sha256"]
        and value["launch_session_id"] == setup["launch_session_id"]
        and value["publication"] == setup["publication"]
        and _exact(value["publication"], ("status", "operation_id"))
        and value["publication"]["status"]
        in {"CURRENT", "PENDING", "NOT_PUBLISHED", "HISTORICAL_HELD"}
        and type(value["attempted"]) is bool
        and value["meaning"] == MEANING
        and all(value[key] is False for key in FALSE_FIELDS)
    ):
        return False
    entry, attempt, status = value["entry"], value["attempt"], value["status"]
    current = value["publication"]["status"] == "CURRENT"
    if entry is not None:
        if not (
            _exact(entry, ENTRY_FIELDS)
            and entry["state"] in {"INCOMPLETE", "ENTERED"}
            and _match(entry["entry_id"], r"cameramode-[0-9a-f]{32}")
            and _match(entry["session_id"], r"physical-camera-[0-9a-f]{32}")
            and _match(entry["cell_id"], r"wizard-physical-camera-[0-9a-f]{16}")
            and all(
                _match(entry[key], r"wizard-[0-9a-f]{32}")
                for key in ("origin_launch_id", "entry_launch_id")
            )
            and all(
                _match(entry[key], r"[0-9a-f]{64}")
                for key in (
                    "entry_sha256",
                    "header_sha256",
                    "selected_identity_sha256",
                    "complete_review_sha256",
                )
            )
            and type(entry["operator_id"]) is str
            and 1 <= len(entry["operator_id"].encode("utf-8")) <= 64
            and entry["operator_id"].strip() == entry["operator_id"]
            and not any(
                ord(char) < 32 or ord(char) == 127 for char in entry["operator_id"]
            )
        ):
            return False
        if current:
            session = setup["session"]
            if (
                any(
                    entry[k] != session["binding"][k] for k in ("session_id", "cell_id")
                )
                or entry["origin_launch_id"] != session["binding"]["launch_id"]
                or entry["header_sha256"]
                != session["verification"]["session"]["header_sha256"]
            ):
                return False
    if attempt is not None:
        if not (
            _exact(attempt, ATTEMPT_FIELDS)
            and value["attempted"] is True
            and _match(attempt["entry_id"], r"cameramode-[0-9a-f]{32}")
            and _match(attempt["entry_sha256"], r"[0-9a-f]{64}")
            and attempt["retention"] in RETENTION
            and type(attempt["event_count"]) is int
            and 0 <= attempt["event_count"] <= 1
            and (attempt["event_count"] == 0 or attempt["retention"] == RETENTION[-1])
            and (
                entry is None
                or all(attempt[k] == entry[k] for k in ("entry_id", "entry_sha256"))
            )
        ):
            return False
    if value["next_action"] != (ACTION if status == "READY_TO_ENTER" else None):
        return False
    if status == "PENDING_PUBLICATION":
        return (
            value["publication"]["status"] == "PENDING"
            and entry is None
            and attempt is None
        )
    if value["publication"]["status"] == "PENDING":
        return False
    if status == "HISTORICAL_HELD":
        return (entry is not None or value["attempted"]) and (
            not current or entry is None
        )
    if status == "NOT_STARTED":
        return entry is None and attempt is None and not value["attempted"]
    if (
        status
        not in {
            "READY_TO_ENTER",
            "ENTERED",
            "ENTERED_PREPARATION_PENDING_REVIEW",
            "INCOMPLETE_HELD",
        }
        or not current
    ):
        return False
    if status == "READY_TO_ENTER":
        if entry is not None or attempt is not None or value["attempted"]:
            return False
    elif entry is None or entry["state"] != (
        "ENTERED"
        if status in {"ENTERED", "ENTERED_PREPARATION_PENDING_REVIEW"}
        else "INCOMPLETE"
    ):
        return False
    stages = setup["session"]["stages"]
    return (
        len(stages) == 15
        and all(row["state"] == "PASS" for row in stages[:4])
        and stages[4]["state"]
        == (
            "BLOCKED"
            if status == "ENTERED_PREPARATION_PENDING_REVIEW"
            else "WAITING_OPERATOR" if status == "ENTERED" else "PENDING"
        )
        and all(row["state"] == "PENDING" for row in stages[5:])
    )
