"""Pure stage-5 entry bytes, without original-store or device authority.

The original owner must authenticate the complete identity history and current
context before retaining this record and committing the next journal event.
Parsing a record or matching caller-supplied hashes cannot perform that audit.
This module has no filesystem, process, camera, serial or publication effects.
"""

from dataclasses import dataclass
import re
from typing import Any

from rocell.providers.windows.owned_worker_process import decode_owned_json
from rocell.providers.windows.usb_identity_protocol import canonical, digest


SCHEMA = "rocell.camera_mode_entry.v1"
SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA = (
    "rocell.physical_camera_source_workflow_readback.v15"
)
CAMERA_MODE_ENTRY_LABEL = re.compile(r"camera-mode-entry-v1:(cameramode-[0-9a-f]{32})")
CAMERA_MODE_ENTRY_EVENT = re.compile(r"CAMERA_MODE_ENTRY_([0-9A-F]{32})")
MAX_ENTRY_BYTES = 16 * 1024
STAGE = "camera_mode_controls"
MEANING = (
    "File-only entry into camera mode/control setup. Original storage, accepted "
    "identity and current configuration require independent owner verification. "
    "No stage PASS, camera probe/capture, runtime release, arm, motion or contact "
    "permission is conferred; operator labels do not authenticate people."
)
HASH_FIELDS = frozenset(
    (
        "source_sha256",
        "header_sha256",
        "prerequisites_sha256",
        "stage_catalog_sha256",
        "stage_order_sha256",
        "stage_policy_sha256",
        "configuration_epochs_sha256",
        # The identity accepted by the final original review, not a relabeled
        # current-launch enrollment. Probe admission must separately establish
        # fresh selection/continuity after a launch or device-context change.
        "selected_identity_sha256",
        "complete_series_sha256",
        "complete_assessment_sha256",
        "complete_review_sha256",
        "complete_review_event_sha256",
    )
)
FALSE_FIELDS = frozenset(
    (
        "physical_authority",
        "hardware_qualified",
        "native_release_allowed",
        "camera_capture_authorized",
        "arm_access_authorized",
        "device_io_performed",
        "authenticated_operator_identity",
    )
)
_CONTEXT_PATTERNS = {
    "cell_id": re.compile(r"wizard-physical-camera-[0-9a-f]{16}\Z"),
    "session_id": re.compile(r"physical-camera-[0-9a-f]{32}\Z"),
    "origin_launch_id": re.compile(r"wizard-[0-9a-f]{32}\Z"),
    "entry_launch_id": re.compile(r"wizard-[0-9a-f]{32}\Z"),
}
_ENTRY_ID = re.compile(r"cameramode-[0-9a-f]{32}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_FIELDS = {
    "schema",
    "stage",
    "effect_class",
    "entry_id",
    "binding",
    "operator_id",
    "recorded_at_utc_ns",
    "meaning",
    *FALSE_FIELDS,
}


class CameraModeEntryError(ValueError):
    """Closed error: never echo original device IDs or operator data."""

    def __init__(self, code: str = "CAMERA_MODE_ENTRY_INVALID") -> None:
        self.code = code
        super().__init__(code)


def _need(ok: bool) -> None:
    if not ok:
        raise CameraModeEntryError()


def _entry_id(value: Any) -> None:
    _need(type(value) is str and _ENTRY_ID.fullmatch(value) is not None)


def camera_mode_operator_valid(value: Any) -> bool:
    """One shared label rule for the form, service and retained entry bytes.

    This is display/audit data, never a pathname or authenticated identity.
    Preserve internal spaces and Unicode, without silently trimming input.
    """
    if (
        type(value) is not str
        or not 0 < len(value) <= 64
        or value != value.strip()
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        return False
    try:
        return len(value.encode("utf-8")) <= 64
    except UnicodeError:
        return False


def _binding(value: Any) -> None:
    _need(type(value) is dict and set(value) == HASH_FIELDS | _CONTEXT_PATTERNS.keys())
    for key in HASH_FIELDS:
        item = value[key]
        _need(
            type(item) is str and _HASH.fullmatch(item) is not None and item != "0" * 64
        )
    for key, pattern in _CONTEXT_PATTERNS.items():
        _need(type(value[key]) is str and pattern.fullmatch(value[key]) is not None)


def _document(payload: bytes) -> dict[str, Any]:
    """Reuse the existing bounded duplicate-key/depth-aware JSON decoder."""
    try:
        value = decode_owned_json(payload, maximum=MAX_ENTRY_BYTES)
        _need(set(value) == _FIELDS and canonical(value) == payload)
        _need(
            value["schema"] == SCHEMA
            and value["stage"] == STAGE
            and value["effect_class"] == "NO_DEVICE_IO"
            and value["meaning"] == MEANING
            and all(value[key] is False for key in FALSE_FIELDS)
        )
        _entry_id(value["entry_id"])
        _binding(value["binding"])
        when, operator = value["recorded_at_utc_ns"], value["operator_id"]
        _need(type(when) is int and 0 < when < 2**63)
        _need(camera_mode_operator_valid(operator))
        return value
    except CameraModeEntryError:
        raise
    except (ValueError, TypeError, KeyError, RecursionError, UnicodeError) as exc:
        raise CameraModeEntryError() from exc


@dataclass(frozen=True, slots=True)
class CameraModeEntry:
    """Immutable bounded data; never a permit or authenticated original."""

    payload: bytes

    def __post_init__(self) -> None:
        _document(self.payload)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        # A detached object prevents a UI consumer from editing retained bytes.
        return _document(self.payload)


def build_camera_mode_entry(
    *,
    entry_id: str,
    binding: dict[str, str],
    operator_id: str,
    recorded_at_utc_ns: int,
) -> CameraModeEntry:
    """Encode owner-supplied context; the builder cannot authenticate its origin."""
    try:
        return CameraModeEntry(
            canonical(
                dict(
                    schema=SCHEMA,
                    stage=STAGE,
                    effect_class="NO_DEVICE_IO",
                    entry_id=entry_id,
                    binding=binding,
                    operator_id=operator_id,
                    recorded_at_utc_ns=recorded_at_utc_ns,
                    meaning=MEANING,
                    **{key: False for key in FALSE_FIELDS},
                )
            )
        )
    except CameraModeEntryError:
        raise
    except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
        raise CameraModeEntryError() from exc


def verify_camera_mode_entry(
    payload: bytes,
    *,
    expected_entry_id: str,
    expected_binding: dict[str, str],
) -> CameraModeEntry:
    """Compare to independently derived context, not to a browser authority flag."""
    _entry_id(expected_entry_id)
    _binding(expected_binding)
    subject = CameraModeEntry(payload)
    value = subject.to_dict()
    _need(
        value["entry_id"] == expected_entry_id
        and canonical(value["binding"]) == canonical(expected_binding)
    )
    return subject


def camera_mode_entry_label(entry_id: str) -> str:
    _entry_id(entry_id)
    return "camera-mode-entry-v1:" + entry_id


def camera_mode_entry_event(entry_id: str) -> str:
    _entry_id(entry_id)
    return "CAMERA_MODE_ENTRY_" + entry_id[len("cameramode-") :].upper()
