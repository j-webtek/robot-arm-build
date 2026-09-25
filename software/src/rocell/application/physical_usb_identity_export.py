"""Complete cached USB diagnostics in bounded, ordinary JSON attachments.

This exporter never reads the original store or touches a device. The service
supplies already retained subjects, including unsuccessful/partial attempts.
Deep and repeated JSON containers are content-addressed so full originals fit
the existing export limits without encoding a private dump or dropping roles.
Credential redaction happens before flattening, while field names still exist.
Reconstruction verifies exported bytes, not commissioning authority.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
from threading import Event
from time import monotonic_ns
from typing import Any, Mapping

from .wizard_diagnostic_export import (
    MAX_ATTACHMENT_BYTES,
    MAX_ATTACHMENTS,
    MAX_EXPORT_BYTES,
    MAX_MANIFEST_BYTES,
    MAX_NODES,
    WizardDiagnosticExporter,
    _json_bytes,
    _parse_json,
    sanitize_diagnostic_record,
)

DIAGNOSTICS_SCHEMA = "rocell.wizard_usb_identity_diagnostics.v1"
DIAGNOSTICS_V2_SCHEMA = "rocell.wizard_usb_identity_diagnostics.v2"
DIAGNOSTICS_V3_SCHEMA = "rocell.wizard_usb_identity_diagnostics.v3"
DIAGNOSTICS_V4_SCHEMA = "rocell.wizard_usb_identity_diagnostics.v4"
DIAGNOSTICS_V5_SCHEMA = "rocell.wizard_usb_identity_diagnostics.v5"
DIAGNOSTICS_V6_SCHEMA = "rocell.wizard_usb_identity_diagnostics.v6"
DIAGNOSTICS_V7_SCHEMA = "rocell.wizard_usb_identity_diagnostics.v7"
EXPORT_SCHEMA = "rocell.usb_identity_diagnostic_export.v1"
EXPORT_V2_SCHEMA = "rocell.usb_identity_diagnostic_export.v2"
EXPORT_V3_SCHEMA = "rocell.usb_identity_diagnostic_export.v3"
EXPORT_V4_SCHEMA = "rocell.usb_identity_diagnostic_export.v4"
EXPORT_V5_SCHEMA = "rocell.usb_identity_diagnostic_export.v5"
EXPORT_V6_SCHEMA = "rocell.usb_identity_diagnostic_export.v6"
EXPORT_V7_SCHEMA = "rocell.usb_identity_diagnostic_export.v7"
_EXPORT_VERSIONS = {
    DIAGNOSTICS_SCHEMA: EXPORT_SCHEMA,
    DIAGNOSTICS_V2_SCHEMA: EXPORT_V2_SCHEMA,
    DIAGNOSTICS_V3_SCHEMA: EXPORT_V3_SCHEMA,
    DIAGNOSTICS_V4_SCHEMA: EXPORT_V4_SCHEMA,
    DIAGNOSTICS_V5_SCHEMA: EXPORT_V5_SCHEMA,
    DIAGNOSTICS_V6_SCHEMA: EXPORT_V6_SCHEMA,
    DIAGNOSTICS_V7_SCHEMA: EXPORT_V7_SCHEMA,
}
PART_SCHEMA = "rocell.usb_identity_diagnostic_part.v1"
MAX_INPUT_BYTES = 6 * 1024 * 1024
MAX_INPUT_NODES = 200_000
MAX_INPUT_DEPTH = 40
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_LAUNCH = re.compile(r"wizard-[0-9a-f]{32}\Z")
_REF = "$usb_diagnostic_node"
_FLAGS = dict(
    physical_authority=False,
    hardware_qualified=False,
    camera_capture_authorized=False,
    arm_access_authorized=False,
)
_KEYS = {
    "schema",
    "source_sha256",
    "launch_session_id",
    "original_context",
    "publication",
    "stage_states",
    "metadata",
    "baseline",
    "inspection_attempt",
    "attempt",
    "meaning",
    *_FLAGS,
}
_MEANING = (
    "Complete supplied cached USB diagnostics only, including partial attempts. "
    "References do not copy earlier stage originals unless included explicitly. "
    "No store readback, device query, hardware qualification or new authority. "
    "Device identifiers, paths and operator labels may be private; review before sharing."
)


class UsbIdentityExportError(ValueError):
    """Malformed cached input, capacity, cancellation or reconstruction failure."""


def _require(ok: bool, code: str = "USB_DIAGNOSTIC_EXPORT_INVALID") -> None:
    if not ok:
        raise UsbIdentityExportError(code)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _digest(value: Any) -> bool:
    return type(value) is str and _SHA.fullmatch(value) is not None


def _copy(value: Any) -> Any:
    """Bound input before recursion/hashing; reject objects and cyclic trees."""
    remaining = MAX_INPUT_NODES

    def visit(item: Any, depth: int) -> Any:
        nonlocal remaining
        remaining -= 1
        _require(remaining >= 0 and depth <= MAX_INPUT_DEPTH, "USB_EXPORT_INPUT_LIMIT")
        if item is None or type(item) is bool:
            return item
        if type(item) is int:
            _require(-(2**63) <= item < 2**63)
            return item
        if type(item) is float:
            _require(math.isfinite(item))
            return item
        if type(item) is str:
            _require(len(item) <= 64 * 1024)
            _require(not any(ord(c) < 32 and c not in "\n\r\t" for c in item))
            return item
        if type(item) is list:
            _require(len(item) <= MAX_INPUT_NODES)
            return [visit(child, depth + 1) for child in item]
        _require(type(item) is dict and len(item) <= MAX_INPUT_NODES)
        result = {}
        for key, child in item.items():
            _require(type(key) is str and 0 < len(key) <= 128)
            _require(not any(ord(c) < 32 for c in key))
            result[key] = visit(child, depth + 1)
        return result

    result = visit(value, 0)
    _require(len(_canonical(result)) <= MAX_INPUT_BYTES, "USB_EXPORT_INPUT_LIMIT")
    return result


def _input(value: Any) -> dict[str, Any]:
    result = _copy(value)
    _require(type(result) is dict)
    schema = result.get("schema")
    _require(type(schema) is str and schema in _EXPORT_VERSIONS)
    trial_keys = {"qualification_trial"} if schema != DIAGNOSTICS_SCHEMA else set()
    phase_keys = (
        {"qualification_baseline", "qualification_attempt"}
        if schema
        in (
            DIAGNOSTICS_V3_SCHEMA,
            DIAGNOSTICS_V4_SCHEMA,
            DIAGNOSTICS_V5_SCHEMA,
            DIAGNOSTICS_V6_SCHEMA,
            DIAGNOSTICS_V7_SCHEMA,
        )
        else set()
    )
    absence_keys = (
        {"qualification_absence", "qualification_absence_attempt"}
        if schema
        in (
            DIAGNOSTICS_V4_SCHEMA,
            DIAGNOSTICS_V5_SCHEMA,
            DIAGNOSTICS_V6_SCHEMA,
            DIAGNOSTICS_V7_SCHEMA,
        )
        else set()
    )
    reconnect_keys = (
        {"qualification_reconnect", "qualification_reconnect_attempt"}
        if schema
        in (DIAGNOSTICS_V5_SCHEMA, DIAGNOSTICS_V6_SCHEMA, DIAGNOSTICS_V7_SCHEMA)
        else set()
    )
    reboot_keys = (
        {"qualification_reboot", "qualification_reboot_attempt"}
        if schema in (DIAGNOSTICS_V6_SCHEMA, DIAGNOSTICS_V7_SCHEMA)
        else set()
    )
    complete_keys = (
        {"qualification_complete", "qualification_complete_attempt"}
        if schema == DIAGNOSTICS_V7_SCHEMA
        else set()
    )
    _require(
        set(result)
        == _KEYS
        | trial_keys
        | phase_keys
        | absence_keys
        | reconnect_keys
        | reboot_keys
        | complete_keys
    )
    if trial_keys:
        # This is a complete cached original, not a caller-supplied qualification
        # verdict. Partial original writes are deliberately exportable too.
        trial = result["qualification_trial"]
        _require(
            type(trial) is dict
            and set(trial)
            == {"trial_id", "state", "request_event", "declaration_event", "plan"}
        )
        _require(
            type(trial["trial_id"]) is str
            and bool(re.fullmatch(r"usbtrial-[0-9a-f]{32}", trial["trial_id"]))
        )
        _require(
            trial["state"]
            in ("INCOMPLETE", "PLAN_RETAINED_NOT_COMMITTED", "PLAN_DECLARED")
        )
        _require(type(trial["request_event"]) is dict)
        for key in ("declaration_event", "plan"):
            _require(trial[key] is None or type(trial[key]) is dict)
    if phase_keys:
        phase = result["qualification_baseline"]
        attempt = result["qualification_attempt"]
        _require(attempt is None or type(attempt) is dict)
        if phase is not None:
            _phase_input(phase)
    if absence_keys:
        absence = result["qualification_absence"]
        attempt = result["qualification_absence_attempt"]
        _require(attempt is None or type(attempt) is dict)
        if absence is not None:
            _absence_input(absence)
    if reconnect_keys:
        reconnect = result["qualification_reconnect"]
        attempt = result["qualification_reconnect_attempt"]
        _require(attempt is None or type(attempt) is dict)
        if reconnect is not None:
            _reconnect_input(reconnect)
    if reboot_keys:
        reboot = result["qualification_reboot"]
        attempt = result["qualification_reboot_attempt"]
        _require(attempt is None or type(attempt) is dict)
        if reboot is not None:
            _reboot_input(reboot)
    if complete_keys:
        _complete_input(
            result["qualification_complete"], result["qualification_complete_attempt"]
        )
    _require(_digest(result["source_sha256"]))
    _require(type(result["launch_session_id"]) is str)
    _require(_LAUNCH.fullmatch(result["launch_session_id"]) is not None)
    _require(all(result[key] is False for key in _FLAGS))
    _require(type(result["publication"]) is dict and type(result["meaning"]) is str)
    for name in (
        "original_context",
        "stage_states",
        "metadata",
        "baseline",
        "inspection_attempt",
        "attempt",
    ):
        _require(result[name] is None or type(result[name]) is dict)
    return result


def _complete_input(complete: Any, attempt: Any) -> None:
    """Closed v14 diagnostic roster; never reconstruct a passing original."""
    from .physical_camera_usb_complete_constants import (
        USB_COMPLETE_ROLE_BYTES,
        USB_COMPLETE_STATES,
    )

    def series_id(value):
        return (
            type(value) is str
            and re.fullmatch(r"usbseries-[0-9a-f]{32}", value) is not None
        )

    def roles(records):
        _require(type(records) is dict and set(records) <= set(USB_COMPLETE_ROLE_BYTES))
        for role, record in records.items():
            if record is not None:
                _require(type(record) is dict and type(record.get("document")) is dict)
                _require(
                    len(_canonical(record["document"])) <= USB_COMPLETE_ROLE_BYTES[role]
                )

    _require(complete is None or type(complete) is dict)
    _require(attempt is None or type(attempt) is dict)
    if complete is not None:
        _require(
            set(complete)
            == {
                "series_id",
                "state",
                "events",
                "series",
                "assessment",
                "review",
                "meaning",
            }
        )
        _require(
            series_id(complete["series_id"])
            and complete["state"] in USB_COMPLETE_STATES
        )
        _require(
            type(complete["events"]) is list
            and 1 <= len(complete["events"]) <= 3
            and all(type(event) is dict for event in complete["events"])
            and type(complete["meaning"]) is str
        )
        roles({role: complete[role] for role in USB_COMPLETE_ROLE_BYTES})
    if attempt is not None:
        _require(set(attempt) == {"action_id", "series_id", "records", "events"})
        _require(
            attempt["action_id"]
            in {"physical_usb_complete_assess", "physical_usb_complete_review"}
            and series_id(attempt["series_id"])
            and type(attempt["events"]) is list
            and len(attempt["events"]) <= 2
            and all(type(event) is dict for event in attempt["events"])
        )
        roles(attempt["records"])


def _phase_input(phase: Any) -> None:
    """Closed cached v10 shape, not reconstruction of original-store authority.

    Retain incomplete phases and nonterminal campaign records in full. Their
    semantics are checked by the original reader; an export never upgrades them.
    """
    roles = {
        "enrollment",
        "preparation",
        "policy_review",
        "runtime_review",
        "identity",
        "boot_request",
        "host_boot",
        "execution",
        "phase_record",
    }
    _require(
        type(phase) is dict
        and set(phase)
        == roles
        | {
            "phase_id",
            "phase",
            "state",
            "events",
            "original_campaign",
            "original_campaign_event",
        }
    )
    _require(
        type(phase["phase_id"]) is str
        and re.fullmatch(r"usbphase-[0-9a-f]{32}", phase["phase_id"]) is not None
        and phase["phase"] == "BASELINE"
        and type(phase["state"]) is str
        and phase["state"]
        in {
            "ENTERED",
            "PREPARATION_REQUESTED",
            "PREPARED",
            "REVIEWED",
            "BOOT_REQUESTED",
            "BOOT_RETAINED",
            "BOOT_HELD",
            "BOOT_UNCERTAIN",
            "QUERY_REQUESTED",
            "ORIGINAL_CAMPAIGN_HELD",
            "RETAINED_BLOCKED",
            "INCOMPLETE",
        }
        and type(phase["events"]) is list
        and 1 <= len(phase["events"]) <= 8
        and all(type(event) is dict for event in phase["events"])
    )
    for name in roles | {"original_campaign", "original_campaign_event"}:
        _require(phase[name] is None or type(phase[name]) is dict)


def _absence_input(phase: Any) -> None:
    """Preserve the closed v11 cache, including interrupted original effects.

    The shared roster is deliberately separate from the older endpoint-only
    absence codec. This checks diagnostic structure, not original admission or
    the truth of a physical observation. The original reader owns those joins.
    """
    from .physical_camera_usb_absence_constants import (
        MAX_USB_ABSENCE_EVENTS,
        USB_ABSENCE_ROLE_BYTES,
        USB_ABSENCE_STATES,
    )

    roles = set(USB_ABSENCE_ROLE_BYTES)
    _require(
        type(phase) is dict
        and set(phase)
        == roles
        | {
            "phase_id",
            "phase",
            "state",
            "events",
            "original_campaign",
            "original_campaign_event",
        }
    )
    _require(
        type(phase["phase_id"]) is str
        and re.fullmatch(r"usbphase-[0-9a-f]{32}", phase["phase_id"]) is not None
        and phase["phase"] == "RECONNECT_ABSENCE"
        and type(phase["state"]) is str
        and phase["state"] in USB_ABSENCE_STATES
        and type(phase["events"]) is list
        and 1 <= len(phase["events"]) <= MAX_USB_ABSENCE_EVENTS
        and all(type(event) is dict for event in phase["events"])
    )
    for name in roles | {"original_campaign", "original_campaign_event"}:
        _require(phase[name] is None or type(phase[name]) is dict)


def _reconnect_input(phase: Any) -> None:
    """Full v12 cached shape, including interrupted/uncertain original work.

    Export preserves every supplied role and campaign. It does not authenticate
    the source store, require a successful measurement or grant replay authority.
    The version-specific roster cannot be hidden in a legacy export envelope.
    """
    from .physical_camera_usb_reconnect_constants import (
        MAX_USB_RECONNECT_EVENTS,
        USB_RECONNECT_ROLE_BYTES,
        USB_RECONNECT_STATES,
    )

    roles = set(USB_RECONNECT_ROLE_BYTES)
    _require(
        type(phase) is dict
        and set(phase)
        == roles
        | {
            "phase_id",
            "phase",
            "state",
            "events",
            "original_campaign",
            "original_campaign_event",
        }
    )
    _require(
        type(phase["phase_id"]) is str
        and re.fullmatch(r"usbphase-[0-9a-f]{32}", phase["phase_id"]) is not None
        and phase["phase"] == "AFTER_RECONNECT"
        and type(phase["state"]) is str
        and phase["state"] in USB_RECONNECT_STATES
        and type(phase["events"]) is list
        and 1 <= len(phase["events"]) <= MAX_USB_RECONNECT_EVENTS
        and all(type(event) is dict for event in phase["events"])
    )
    for name in roles | {"original_campaign", "original_campaign_event"}:
        _require(phase[name] is None or type(phase[name]) is dict)


def _reboot_input(phase: Any) -> None:
    """Closed v13 diagnostics, including partial and uncertain original work.

    Preserve every supplied byte-bearing record, not a synthetic successful
    reboot. The original reader, not this cached export, authenticates events,
    permits, new-launch eligibility and the independently observed restart.
    """
    from .physical_camera_usb_reboot_constants import (
        MAX_USB_REBOOT_EVENTS,
        USB_REBOOT_ROLE_BYTES,
        USB_REBOOT_STATES,
    )

    roles = set(USB_REBOOT_ROLE_BYTES)
    _require(
        type(phase) is dict
        and set(phase)
        == roles
        | {
            "phase_id",
            "phase",
            "state",
            "events",
            "original_campaign",
            "original_campaign_event",
        }
    )
    _require(
        type(phase["phase_id"]) is str
        and re.fullmatch(r"usbphase-[0-9a-f]{32}", phase["phase_id"]) is not None
        and phase["phase"] == "AFTER_REBOOT"
        and type(phase["state"]) is str
        and phase["state"] in USB_REBOOT_STATES
        and type(phase["events"]) is list
        and 1 <= len(phase["events"]) <= MAX_USB_REBOOT_EVENTS
        and all(type(event) is dict for event in phase["events"])
    )
    for name in roles | {"original_campaign", "original_campaign_event"}:
        _require(phase[name] is None or type(phase[name]) is dict)


def _subjects(value: Any) -> dict[str, tuple[dict[str, Any], str]]:
    """Index supplied record payloads; references alone are not copied evidence."""
    result: dict[str, tuple[dict[str, Any], str]] = {}

    def visit(item: Any, path: str) -> None:
        if type(item) is dict:
            if "evidence_sha256" in item:
                # Stage-role records use document; original campaign records use
                # evidence. A partial terminal record may have neither payload.
                key = "document" if "document" in item else "evidence"
                document = item.get(key)
                if document is not None:
                    _require(
                        type(document) is dict and _digest(item["evidence_sha256"])
                    )
                    result[path] = (document, item["evidence_sha256"])
            for key, child in item.items():
                # JSON Pointer escaping keeps arbitrary labels unambiguous.
                visit(child, path + "/" + key.replace("~", "~0").replace("/", "~1"))
        elif type(item) is list:
            for index, child in enumerate(item):
                visit(child, path + "/" + str(index))

    visit(value, "")
    return result


def _redact(value: Any) -> Any:
    """Apply existing field/text redaction rules before removing nesting."""
    secrets: dict[str, bool] = {}

    def visit(item: Any) -> Any:
        if type(item) is dict:
            result = {}
            for key, child in item.items():
                if key not in secrets:
                    secrets[key] = (
                        sanitize_diagnostic_record({key: None})[key] == "[REDACTED]"
                    )
                result[key] = "[REDACTED]" if secrets[key] else visit(child)
            return result
        if type(item) is list:
            return [visit(child) for child in item]
        return sanitize_diagnostic_record(item, maximum_bytes=MAX_ATTACHMENT_BYTES)

    return visit(value)


def _flatten(value: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    nodes: dict[str, Any] = {}

    def visit(item: Any) -> Any:
        if type(item) is dict:
            node = dict(
                kind="object",
                values=[[key, visit(child)] for key, child in sorted(item.items())],
            )
        elif type(item) is list:
            node = dict(kind="array", values=[visit(child) for child in item])
        else:
            return item
        digest = _hash(node)
        nodes[digest] = node
        return {_REF: digest}

    return visit(value)[_REF], nodes


def _expand(root: str, nodes: dict[str, Any]) -> dict[str, Any]:
    _require(_digest(root) and 0 < len(nodes) <= MAX_INPUT_NODES)
    for digest, node in nodes.items():
        _require(_digest(digest) and type(node) is dict)
        _require(
            set(node) == {"kind", "values"} and node["kind"] in ("object", "array")
        )
        _require(type(node["values"]) is list and _hash(node) == digest)
    used: set[str] = set()
    active: set[str] = set()
    remaining = MAX_INPUT_NODES

    def visit(item: Any, depth: int) -> Any:
        nonlocal remaining
        remaining -= 1
        _require(remaining >= 0 and depth <= MAX_INPUT_DEPTH)
        if type(item) is not dict:
            _require(type(item) is not list)
            return item
        _require(set(item) == {_REF} and _digest(item[_REF]))
        digest = item[_REF]
        _require(digest in nodes and digest not in active)
        active.add(digest)
        used.add(digest)
        node = nodes[digest]
        if node["kind"] == "array":
            result: Any = [visit(child, depth + 1) for child in node["values"]]
        else:
            result = {}
            for pair in node["values"]:
                _require(type(pair) is list and len(pair) == 2 and type(pair[0]) is str)
                _require(pair[0] not in result)
                result[pair[0]] = visit(pair[1], depth + 1)
            _require(list(result) == sorted(result))
        active.remove(digest)
        return result

    result = visit({_REF: root}, 0)
    _require(used == set(nodes))
    return _input(result)


def _count(value: Any) -> int:
    children = (
        value.values() if type(value) is dict else value if type(value) is list else ()
    )
    return 1 + sum(_count(child) for child in children)


def _parts(root: str, nodes: dict[str, Any]) -> dict[str, bytes]:
    """Largest-first bounded packing; final sizes use the actual serializer."""
    groups: list[dict[str, Any]] = []
    sizes: list[tuple[int, int]] = []
    entries = []
    for digest, node in nodes.items():
        raw = _json_bytes({digest: node})
        cost, count = len(raw) + 4 * raw.count(b"\n") + 128, _count(node)
        _require(
            cost < MAX_ATTACHMENT_BYTES - 4096 and count < MAX_NODES - 64,
            "USB_EXPORT_CAPACITY",
        )
        entries.append((cost, digest, count, node))
    for cost, digest, count, node in sorted(entries, key=lambda row: (-row[0], row[1])):
        slot = next(
            (
                i
                for i, (size, items) in enumerate(sizes)
                if size + cost <= MAX_ATTACHMENT_BYTES - 4096
                and items + count <= MAX_NODES - 64
            ),
            None,
        )
        if slot is None:
            _require(len(groups) < MAX_ATTACHMENTS, "USB_EXPORT_CAPACITY")
            slot = len(groups)
            groups.append({})
            sizes.append((0, 0))
        groups[slot][digest] = node
        size, items = sizes[slot]
        sizes[slot] = size + cost, items + count
    result = {}
    for index, group in enumerate(groups, 1):
        packet = dict(
            schema=PART_SCHEMA,
            part_index=index,
            part_count=len(groups),
            root_sha256=root,
            nodes=group,
            **_FLAGS,
        )
        _require(
            sanitize_diagnostic_record(packet, maximum_bytes=MAX_ATTACHMENT_BYTES)
            == packet,
            "USB_EXPORT_REDACTION_UNSTABLE",
        )
        result[f"usb-identity-part-{index:02d}.json"] = _json_bytes(packet)
    return result


def _summary(value: dict[str, Any]) -> dict[str, Any]:
    """Small operator index; the exact role graph remains the full diagnostic."""
    baseline = value["baseline"] or {}
    attempt = value["attempt"] or {}
    dispatch = attempt.get("dispatch")
    dispatch = dispatch if type(dispatch) is dict else {}
    view = dispatch.get("dispatch")
    view = view if type(view) is dict else {}
    original = dispatch.get("original")
    original = original if type(original) is dict else {}

    def label(document: dict[str, Any], name: str) -> Any:
        item = document.get(name)
        return item if type(item) is str and len(item) <= 128 else None

    result = dict(
        publication_status=label(value["publication"], "status"),
        baseline_state=label(baseline, "state"),
        usb_id=label(baseline, "usb_id") or label(attempt, "usb_id"),
        attempt_action=label(attempt, "action_id"),
        dispatch_phase=label(view, "phase"),
        dispatch_error=label(view, "error_code"),
        original_retention=label(original, "retention"),
        subject_count=len(_subjects(value)),
        meaning="CACHED_INDEX_ONLY_SEE_COMPLETE_PARTS_AND_COVERAGE",
    )
    if value["schema"] != DIAGNOSTICS_SCHEMA:
        trial = value["qualification_trial"]
        plan = trial["plan"] or {}
        result.update(
            qualification_trial_id=trial["trial_id"],
            qualification_state=trial["state"],
            qualification_plan_sha256=label(plan, "evidence_sha256"),
        )
    if value["schema"] in (
        DIAGNOSTICS_V3_SCHEMA,
        DIAGNOSTICS_V4_SCHEMA,
        DIAGNOSTICS_V5_SCHEMA,
        DIAGNOSTICS_V6_SCHEMA,
        DIAGNOSTICS_V7_SCHEMA,
    ):
        phase = value["qualification_baseline"] or {}
        phase_record = phase.get("phase_record") or {}
        result.update(
            qualification_phase_id=label(phase, "phase_id"),
            qualification_baseline_state=label(phase, "state"),
            qualification_baseline_sha256=label(phase_record, "evidence_sha256"),
        )
    if value["schema"] in (
        DIAGNOSTICS_V4_SCHEMA,
        DIAGNOSTICS_V5_SCHEMA,
        DIAGNOSTICS_V6_SCHEMA,
        DIAGNOSTICS_V7_SCHEMA,
    ):
        absence = value["qualification_absence"] or {}
        absence_record = absence.get("phase_record") or {}
        result.update(
            qualification_absence_phase_id=label(absence, "phase_id"),
            qualification_absence_state=label(absence, "state"),
            qualification_absence_sha256=label(absence_record, "evidence_sha256"),
        )
    if value["schema"] in (
        DIAGNOSTICS_V5_SCHEMA,
        DIAGNOSTICS_V6_SCHEMA,
        DIAGNOSTICS_V7_SCHEMA,
    ):
        reconnect = value["qualification_reconnect"] or {}
        reconnect_record = reconnect.get("phase_record") or {}
        result.update(
            qualification_reconnect_phase_id=label(reconnect, "phase_id"),
            qualification_reconnect_state=label(reconnect, "state"),
            qualification_reconnect_sha256=label(reconnect_record, "evidence_sha256"),
        )
    if value["schema"] in (DIAGNOSTICS_V6_SCHEMA, DIAGNOSTICS_V7_SCHEMA):
        reboot = value["qualification_reboot"] or {}
        reboot_record = reboot.get("phase_record") or {}
        result.update(
            qualification_reboot_phase_id=label(reboot, "phase_id"),
            qualification_reboot_state=label(reboot, "state"),
            qualification_reboot_sha256=label(reboot_record, "evidence_sha256"),
        )
    if value["schema"] == DIAGNOSTICS_V7_SCHEMA:
        complete = value["qualification_complete"] or {}
        result.update(
            qualification_complete_series_id=label(complete, "series_id"),
            qualification_complete_state=label(complete, "state"),
            qualification_complete_assessment_sha256=label(
                complete.get("assessment") or {}, "evidence_sha256"
            ),
            qualification_complete_review_sha256=label(
                complete.get("review") or {}, "evidence_sha256"
            ),
        )
    return result


def prepare_usb_identity_diagnostics_export(
    diagnostics: dict[str, Any],
    *,
    source_sha256: str,
    launch_id: str,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Pure preflight and full reconstruction; any refusal precedes writes."""
    _require(
        _digest(source_sha256)
        and type(launch_id) is str
        and bool(_LAUNCH.fullmatch(launch_id))
    )
    original = _input(diagnostics)
    # An export from a held service retains that service's source identity;
    # a different current checkout is not a replacement label for its bytes.
    _require(original["source_sha256"] == source_sha256, "USB_EXPORT_SOURCE_MISMATCH")
    subjects = _subjects(original)
    _require(
        all(_hash(doc) == expected for doc, expected in subjects.values()),
        "USB_EXPORT_SUBJECT_HASH",
    )
    cleaned = _redact(original)
    clean_subjects = _subjects(cleaned)
    _require(set(subjects) == set(clean_subjects))
    root, nodes = _flatten(cleaned)
    parts = _parts(root, nodes)
    preserved = original == cleaned
    snapshot = dict(
        schema=_EXPORT_VERSIONS[original["schema"]],
        session_id=launch_id,
        mode="PHYSICAL_DIAGNOSTIC",
        source_binding_sha256=source_sha256,
        source_identity=dict(source_sha256=source_sha256),
        original_diagnostics_sha256=_hash(original),
        exported_diagnostics_sha256=_hash(cleaned),
        original_bytes_preserved=preserved,
        credential_redaction_applied=not preserved,
        root_sha256=root,
        node_count=len(nodes),
        summary=_summary(cleaned),
        reconstruction_status=(
            "ORIGINAL_BYTES_RECONSTRUCTIBLE"
            if preserved
            else "REDACTED_ORIGINAL_NOT_RECONSTRUCTIBLE"
        ),
        coverage=[
            dict(
                path=path,
                evidence_sha256=expected,
                exported_document_sha256=_hash(clean_subjects[path][0]),
                original_bytes_preserved=doc == clean_subjects[path][0],
            )
            for path, (doc, expected) in sorted(subjects.items())
        ],
        parts=[
            dict(
                attachment="attachment-" + name,
                bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(),
            )
            for name, raw in parts.items()
        ],
        meaning=_MEANING,
        **_FLAGS,
    )
    _require(sanitize_diagnostic_record(snapshot) == snapshot)
    _require(
        sum(map(len, parts.values()))
        + len(_json_bytes(snapshot))
        + MAX_MANIFEST_BYTES
        + 16 * 1024
        <= MAX_EXPORT_BYTES,
        "USB_EXPORT_CAPACITY",
    )
    _require(restore_usb_identity_diagnostics(snapshot, parts) == cleaned)
    return snapshot, parts


def restore_usb_identity_diagnostics(
    snapshot: dict[str, Any],
    attachments: Mapping[str, bytes],
    *,
    expected_original_diagnostics_sha256: str | None = None,
) -> dict[str, Any]:
    """Reconstruct complete supplied metadata, with explicit redaction status."""
    data = _copy(snapshot)
    keys = {
        "schema",
        "session_id",
        "mode",
        "source_binding_sha256",
        "source_identity",
        "original_diagnostics_sha256",
        "exported_diagnostics_sha256",
        "original_bytes_preserved",
        "credential_redaction_applied",
        "root_sha256",
        "node_count",
        "reconstruction_status",
        "coverage",
        "summary",
        "parts",
        "meaning",
        *_FLAGS,
    }
    _require(
        type(data) is dict
        and set(data) == keys
        and data["schema"] in _EXPORT_VERSIONS.values()
    )
    _require(all(data[key] is False for key in _FLAGS))
    _require(data["mode"] == "PHYSICAL_DIAGNOSTIC" and data["meaning"] == _MEANING)
    for key in (
        "source_binding_sha256",
        "original_diagnostics_sha256",
        "exported_diagnostics_sha256",
        "root_sha256",
    ):
        _require(_digest(data[key]))
    _require(
        type(data["session_id"]) is str and bool(_LAUNCH.fullmatch(data["session_id"]))
    )
    _require(
        data["source_identity"] == {"source_sha256": data["source_binding_sha256"]}
    )
    if expected_original_diagnostics_sha256 is not None:
        _require(
            _digest(expected_original_diagnostics_sha256)
            and data["original_diagnostics_sha256"]
            == expected_original_diagnostics_sha256
        )
    preserved = data["original_bytes_preserved"]
    _require(
        type(preserved) is bool
        and data["credential_redaction_applied"] is not preserved
    )
    _require(
        (data["original_diagnostics_sha256"] == data["exported_diagnostics_sha256"])
        is preserved
    )
    _require(
        data["reconstruction_status"]
        == (
            "ORIGINAL_BYTES_RECONSTRUCTIBLE"
            if preserved
            else "REDACTED_ORIGINAL_NOT_RECONSTRUCTIBLE"
        )
    )
    rows = data["parts"]
    _require(type(rows) is list and 1 <= len(rows) <= MAX_ATTACHMENTS)
    _require(isinstance(attachments, Mapping) and len(attachments) == len(rows))
    nodes: dict[str, Any] = {}
    expected_names = set()
    total = 0
    for index, row in enumerate(rows, 1):
        _require(type(row) is dict and set(row) == {"attachment", "bytes", "sha256"})
        name = f"attachment-usb-identity-part-{index:02d}.json"
        _require(
            row["attachment"] == name
            and type(row["bytes"]) is int
            and _digest(row["sha256"])
        )
        plain = name.removeprefix("attachment-")
        selected = name if name in attachments else plain
        expected_names.add(selected)
        raw = attachments.get(selected)
        _require(type(raw) is bytes and 0 < len(raw) <= MAX_ATTACHMENT_BYTES)
        assert isinstance(raw, bytes)  # The exact-type check above is authoritative.
        total += len(raw)
        _require(
            total <= MAX_EXPORT_BYTES
            and len(raw) == row["bytes"]
            and hashlib.sha256(raw).hexdigest() == row["sha256"]
        )
        packet = _parse_json(raw)
        _require(
            type(packet) is dict
            and set(packet)
            == {"schema", "part_index", "part_count", "root_sha256", "nodes", *_FLAGS}
        )
        _require(
            packet["schema"] == PART_SCHEMA
            and type(packet["part_index"]) is int
            and packet["part_index"] == index
        )
        _require(
            type(packet["part_count"]) is int
            and packet["part_count"] == len(rows)
            and packet["root_sha256"] == data["root_sha256"]
        )
        _require(
            all(packet[key] is False for key in _FLAGS)
            and type(packet["nodes"]) is dict
        )
        _require(
            sanitize_diagnostic_record(packet, maximum_bytes=MAX_ATTACHMENT_BYTES)
            == packet
            and _json_bytes(packet) == raw
        )
        _require(not set(nodes).intersection(packet["nodes"]))
        nodes.update(packet["nodes"])
    _require(set(attachments) == expected_names)
    _require(type(data["node_count"]) is int and data["node_count"] == len(nodes))
    result = _expand(data["root_sha256"], nodes)
    _require(
        data["schema"] == _EXPORT_VERSIONS[result["schema"]],
        "USB_EXPORT_SCHEMA_MISMATCH",
    )
    _require(
        result["source_sha256"] == data["source_binding_sha256"],
        "USB_EXPORT_SOURCE_MISMATCH",
    )
    _require(
        _hash(result) == data["exported_diagnostics_sha256"]
        and _redact(result) == result
    )
    subjects = _subjects(result)
    _require(data["summary"] == _summary(result))
    expected_coverage = [
        dict(
            path=path,
            evidence_sha256=expected,
            exported_document_sha256=_hash(doc),
            original_bytes_preserved=_hash(doc) == expected,
        )
        for path, (doc, expected) in sorted(subjects.items())
    ]
    _require(data["coverage"] == expected_coverage)
    _require(
        not preserved
        or all(row["original_bytes_preserved"] for row in expected_coverage)
    )
    return result


def export_usb_identity_diagnostics(
    diagnostics: dict[str, Any],
    *,
    export_parent: Path,
    source_sha256: str,
    launch_id: str,
    cancellation: Event,
    deadline_ns: int,
) -> dict[str, Any]:
    """Create one fresh verified export under the explicitly assigned parent."""
    now = monotonic_ns()
    _require(
        isinstance(cancellation, Event)
        and type(deadline_ns) is int
        and now < deadline_ns <= now + 120_000_000_000
    )

    def check() -> None:
        _require(not cancellation.is_set(), "USB_EXPORT_CANCELLED")
        _require(monotonic_ns() < deadline_ns, "USB_EXPORT_TIMED_OUT")

    check()
    snapshot, attachments = prepare_usb_identity_diagnostics_export(
        diagnostics,
        source_sha256=source_sha256,
        launch_id=launch_id,
    )
    check()
    exporter = WizardDiagnosticExporter(export_parent)
    exporter.prepare(create=True)
    check()
    return exporter.export(snapshot, [], attachments=attachments)
