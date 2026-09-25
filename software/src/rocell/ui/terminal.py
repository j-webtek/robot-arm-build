"""Accessible headless adapter to the same service used by the browser.

This module neither imports providers nor owns service cleanup. A command is
selected from the current server projection, prepared without effects, then
executed only after an explicit exact-ticket confirmation. Polling never
reconnects, retries, energizes, or dispatches another action.
"""

from __future__ import annotations

import json
import math
import re
import time
import unicodedata
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from rocell.ui.server import WizardService


POLL_INTERVAL_S = 0.25
POLL_WINDOW_STEPS = 60
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_TERMINAL_STATES = frozenset({"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"})
_FIELD_KEYS = frozenset(
    {
        "name",
        "label",
        "type",
        "required",
        "default",
        "options",
        "min",
        "max",
        "step",
        "max_length",
        "placeholder",
        "help",
    }
)
_RESERVED_FIELDS = frozenset(
    {
        "path",
        "port",
        "camera_index",
        "authority",
        "hardware_authority",
        "allow_hardware",
        "command",
        "argv",
        "destination",
        "directory",
        "worker",
        "raw_bytes",
        "t_code",
    }
)


class _Back(Exception):
    """Operator canceled before dispatch; no retry is inferred."""


def _display(value: Any) -> str:
    """Render records as data, not terminal escape/control instructions."""
    rendered = (
        value
        if isinstance(value, str)
        else json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2)
    )
    return "".join(
        (
            character
            if character in "\n\t"
            or not unicodedata.category(character).startswith("C")
            else f"\\u{ord(character):04x}"
        )
        for character in rendered
    )


def _compact_check_data(value: Any) -> str | None:
    """Bound display data independently from the retained evidence verifier."""
    visited = 0

    def bounded(item: Any, depth: int) -> bool:
        nonlocal visited
        visited += 1
        if visited > 128 or depth > 6:
            return False
        if item is None or type(item) is bool:
            return True
        if type(item) is str:
            return len(item) <= 2048
        if type(item) is int:
            return abs(item) <= 9_007_199_254_740_991
        if type(item) is float:
            return math.isfinite(item) and abs(item) <= 9_007_199_254_740_991
        if type(item) is list:
            return len(item) <= 32 and all(bounded(child, depth + 1) for child in item)
        if type(item) is dict:
            return len(item) <= 32 and all(
                type(key) is str and len(key) <= 128 and bounded(child, depth + 1)
                for key, child in item.items()
            )
        return False

    if not bounded(value, 0):
        return None
    rendered = (
        value
        if type(value) is str
        else json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)
    )
    return rendered if len(rendered) <= 4096 else None


_METADATA_FOLLOWUPS = {
    "VERIFY_RECEIVED_MODEL_AND_UNIT",
    "RESOLVE_UNIQUE_IDENTITY_AND_NATIVE_PREOPEN_RECHECK",
    "QUALIFY_NATIVE_BACKEND_AND_CONNECTION_CONTRACT",
    "COMPLETE_CANONICAL_STAGE_AND_PHYSICAL_RELEASE_GATES",
}


_NATIVE_ARM_FIELDS = (
    "persistent_port_path",
    "persistent_instance_id",
    "port_name",
    "vid",
    "pid",
    "driver_provider",
    "driver_service",
    "driver_version",
    "driver_inf",
)
_NATIVE_ARM_BLOCKERS = frozenset(
    {
        "GENERIC_REVIEW_BLOCKED",
        "GENERIC_COLLECTION_INCOMPLETE",
        "NATIVE_COLLECTION_INCOMPLETE",
        "GENERIC_UNIT_NOT_PRESENT",
        "GENERIC_UNIT_AMBIGUOUS",
        "GENERIC_CANDIDATE_CHANGED",
        "GENERIC_PORT_AMBIGUOUS",
        "NATIVE_MAPPING_NOT_PRESENT",
        "NATIVE_MAPPING_AMBIGUOUS",
        "NATIVE_PROPERTIES_INCOMPLETE",
        "NATIVE_REQUIRED_FIELD_MISSING",
        "NATIVE_PORT_AMBIGUOUS",
        "NATIVE_PERSISTENT_PATH_AMBIGUOUS",
        "NATIVE_INSTANCE_AMBIGUOUS",
        "INVALID_COM_METADATA",
    }
)


def _native_arm_metadata(value: Any, view: dict[str, Any]) -> dict[str, Any] | None:
    """Validate cached correlation, not physical identity or port-open authority."""
    v = _CameraConfigurationDisplay
    flags = {"connected", "qualified", "physical_authority"}
    reasons = {
        "ARM_METADATA_CONTEXT_CHANGED",
        "ARM_METADATA_NOT_PUBLISHED",
        "ARM_METADATA_ACTION_FAILED",
        "DIAGNOSTIC_LOG_FAILED",
        "SOURCE_CHANGED",
        "APPLICATION_CLOSED",
    }

    def identifier(item: Any) -> bool:
        return (
            type(item) is str
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", item) is not None
        )

    if (
        not v.exact(
            value, {"schema", "status", "report", "invalidation_reason", *flags}
        )
        or value["schema"] != "rocell.wizard_native_arm_metadata_view.v1"
        or not all(value[key] is False for key in flags)
        or value["status"] not in ("NOT_INSPECTED", "CURRENT", "HISTORICAL_HELD")
        or not (
            value["invalidation_reason"] is None
            or type(value["invalidation_reason"]) is str
            and value["invalidation_reason"] in reasons
        )
        or value["status"] == "NOT_INSPECTED"
        and (value["report"] is not None or value["invalidation_reason"] is not None)
        or value["status"] == "CURRENT"
        and (value["report"] is None or value["invalidation_reason"] is not None)
    ):
        return None
    report = value["report"]
    if report is None:
        return value
    if (
        not v.exact(
            report,
            {
                "schema",
                "status",
                "binding",
                "provenance",
                "report_sha256",
                "snapshot_sha256",
                "counts",
                "native_fields",
                "blockers",
                "persistent_binding",
                *flags,
            },
        )
        or report["schema"] != "rocell.wizard_native_arm_metadata_summary.v1"
        or not all(report[key] is False for key in flags)
        or report["persistent_binding"] is not False
        or report["status"] not in ("METADATA_CORRELATED", "HELD")
        or not v.digest(report["report_sha256"])
        or not v.digest(report["snapshot_sha256"])
        or not v.exact(
            report["binding"],
            {
                "mode",
                "session_id",
                "source_sha256",
                "operation_id",
                "generic_review_sha256",
                "generic_report_sha256",
                "generic_candidate_sha256",
                "generic_inventory_operation_id",
            },
        )
        or report["binding"]["mode"] not in ("physical", "rehearsal")
        or not all(
            identifier(report["binding"][key])
            for key in ("session_id", "operation_id", "generic_inventory_operation_id")
        )
        or not all(
            v.digest(report["binding"][key])
            for key in (
                "source_sha256",
                "generic_review_sha256",
                "generic_report_sha256",
                "generic_candidate_sha256",
            )
        )
        or not v.exact(
            report["provenance"], {"origin", "native_source", "unit_serial_origin"}
        )
        or report["provenance"]["unit_serial_origin"]
        != "GENERIC_SERIAL_INVENTORY_NOT_USB_DESCRIPTOR"
        or (report["provenance"]["origin"], report["provenance"]["native_source"])
        != (
            ("PHYSICAL_OBSERVATION", "WINDOWS_CM_METADATA")
            if report["binding"]["mode"] == "physical"
            else ("SYNTHETIC_REHEARSAL", "INJECTED_CM_METADATA")
        )
        or not v.exact(
            report["counts"],
            {
                "serial_candidates",
                "native_observations",
                "generic_matches",
                "native_matches",
            },
        )
        or not all(v.integer(n, 0, 128) for n in report["counts"].values())
        or report["counts"]["generic_matches"] > report["counts"]["serial_candidates"]
        or report["counts"]["native_matches"] > report["counts"]["native_observations"]
        or not v.exact(report["native_fields"], set(_NATIVE_ARM_FIELDS))
        or not all(
            status in ("OBSERVED", "MISSING", "NOT_VERIFIED")
            for status in report["native_fields"].values()
        )
        or type(report["blockers"]) is not list
        or len(report["blockers"]) > 32
        or not all(
            type(code) is str and code in _NATIVE_ARM_BLOCKERS
            for code in report["blockers"]
        )
        or len(set(report["blockers"])) != len(report["blockers"])
        or ((report["status"] == "HELD") != bool(report["blockers"]))
        or report["status"] == "METADATA_CORRELATED"
        and (
            report["counts"]["generic_matches"] != 1
            or report["counts"]["native_matches"] != 1
            or not all(
                status == "OBSERVED" for status in report["native_fields"].values()
            )
        )
    ):
        return None
    if value["status"] == "CURRENT":
        generic = _device_metadata(view.get("device_selection"))
        review = generic["devices"]["SERIAL"]["review"] if generic else None
        binding = report["binding"]
        if (
            generic is None
            or review is None
            or binding["mode"] != view.get("mode")
            or binding["session_id"] != view.get("session_id")
            or binding["source_sha256"] != view.get("source_binding_sha256")
            or generic["provenance"]["mode"] != binding["mode"]
            or generic["provenance"]["session_id"] != binding["session_id"]
            or generic["provenance"]["source_sha256"] != binding["source_sha256"]
            or binding["generic_candidate_sha256"] != review["candidate_sha256"]
            or binding["generic_report_sha256"] != review["report_sha256"]
            or binding["generic_inventory_operation_id"] != review["operation_id"]
        ):
            return None
    return value


def _device_metadata(value: Any) -> dict[str, Any] | None:
    """Validate the cached display contract, never discovery or native identity.

    A structurally valid acknowledgment is still neither a persistent binding
    nor authority. Do not render unknown fields, stale reviews or partial lists.
    """

    def exact(item: Any, keys: set[str]) -> bool:
        return type(item) is dict and set(item) == keys

    def safe_text(item: Any) -> bool:
        return (
            type(item) is str
            and bool(item)
            and not any(0xD800 <= ord(character) <= 0xDFFF for character in item)
            and len(item.encode("utf-8")) <= 2048
            and all(
                ord(character) >= 32 and ord(character) != 127 for character in item
            )
        )

    def optional_text(item: Any) -> bool:
        return item is None or safe_text(item)

    def digest(item: Any) -> bool:
        return type(item) is str and re.fullmatch(r"[a-f0-9]{64}", item) is not None

    def flags(item: dict[str, Any]) -> bool:
        return all(
            item.get(key) is False
            for key in (
                "physical_authority",
                "connected",
                "qualified",
                "persistent_binding",
            )
        )

    def codes(item: Any) -> bool:
        return (
            type(item) is list
            and len(item) <= 32
            and all(
                type(code) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code)
                for code in item
            )
            and len(set(item)) == len(item)
        )

    if not isinstance(value, dict) or not exact(
        value,
        {
            "schema",
            "status",
            "provenance",
            "report_sha256",
            "operation_id",
            "devices",
            "physical_authority",
            "connected",
            "qualified",
            "persistent_binding",
            "invalidation_reason",
        },
    ):
        return None
    if (
        value["schema"] != "rocell.wizard_device_selection.v1"
        or not flags(value)
        or value["status"]
        not in (
            "NO_INVENTORY",
            "METADATA_CANDIDATES_AVAILABLE",
            "METADATA_REVIEW_RECORDED",
            "INVALIDATED",
        )
        or not exact(
            value["provenance"],
            {
                "mode",
                "session_id",
                "source_sha256",
                "platform_system",
                "captured_at_unix_ns",
                "scope",
            },
        )
        or not exact(value["devices"], {"CAMERA", "SERIAL"})
        or not (value["report_sha256"] is None or digest(value["report_sha256"]))
        or not optional_text(value["operation_id"])
        or not optional_text(value["invalidation_reason"])
    ):
        return None
    origin = value["provenance"]
    timestamp = origin["captured_at_unix_ns"]
    if (
        origin["mode"] not in ("rehearsal", "physical")
        or not safe_text(origin["session_id"])
        or not digest(origin["source_sha256"])
        or not optional_text(origin["platform_system"])
        or origin["scope"] != "METADATA_SNAPSHOT_ONLY"
        or not (
            timestamp is None or type(timestamp) is int and 0 <= timestamp <= 2**63 - 1
        )
    ):
        return None
    for kind in ("CAMERA", "SERIAL"):
        device = value["devices"][kind]
        if (
            not exact(device, {"candidates", "review"})
            or type(device["candidates"]) is not list
            or len(device["candidates"]) > 128
        ):
            return None
        ids: set[str] = set()
        for candidate in device["candidates"]:
            if (
                not exact(
                    candidate,
                    {
                        "choice_id",
                        "display_name",
                        "vid",
                        "pid",
                        "unit_serial",
                        "source",
                        "identity_blockers",
                        "candidate_sha256",
                    },
                )
                or not safe_text(candidate["choice_id"])
                or candidate["choice_id"] in ids
                or not safe_text(candidate["display_name"])
                or not all(
                    item is None
                    or type(item) is str
                    and re.fullmatch(r"[a-f0-9]{4}", item)
                    for item in (candidate["vid"], candidate["pid"])
                )
                or not optional_text(candidate["unit_serial"])
                or not digest(candidate["candidate_sha256"])
                or not codes(candidate["identity_blockers"])
                or candidate["source"]
                not in (
                    ("WINDOWS_PNP", "LINUX_SYSFS")
                    if kind == "CAMERA"
                    else ("PYSERIAL_LIST_PORTS", "INJECTED_SERIAL_ENUMERATOR")
                )
            ):
                return None
            ids.add(candidate["choice_id"])
        review = device["review"]
        if review is not None and (
            not exact(
                review,
                {
                    "choice_id",
                    "candidate_sha256",
                    "reviewer_id",
                    "report_sha256",
                    "operation_id",
                    "status",
                    "connected",
                    "qualified",
                    "persistent_binding",
                    "physical_authority",
                    "followup_requirements",
                },
            )
            or not flags(review)
            or review["status"] != "METADATA_ACKNOWLEDGED_FOR_INVESTIGATION"
            or not safe_text(review["reviewer_id"])
            or review["report_sha256"] != value["report_sha256"]
            or review["operation_id"] != value["operation_id"]
            or not any(
                row["choice_id"] == review["choice_id"]
                and row["candidate_sha256"] == review["candidate_sha256"]
                for row in device["candidates"]
            )
            or not codes(review["followup_requirements"])
            or set(review["followup_requirements"]) != _METADATA_FOLLOWUPS
        ):
            return None
    if value["status"] in ("NO_INVENTORY", "INVALIDATED"):
        if (
            value["report_sha256"] is not None
            or value["operation_id"] is not None
            or origin["platform_system"] is not None
            or timestamp is not None
            or any(
                value["devices"][kind]["candidates"]
                or value["devices"][kind]["review"] is not None
                for kind in ("CAMERA", "SERIAL")
            )
            or (
                value["status"] == "NO_INVENTORY"
                and value["invalidation_reason"] is not None
            )
            or (
                value["status"] == "INVALIDATED"
                and not safe_text(value["invalidation_reason"])
            )
        ):
            return None
    elif (
        not digest(value["report_sha256"])
        or not safe_text(value["operation_id"])
        or value["invalidation_reason"] is not None
        or any(
            value["devices"][kind]["review"] is not None
            for kind in ("CAMERA", "SERIAL")
        )
        != (value["status"] == "METADATA_REVIEW_RECORDED")
    ):
        return None
    return value


def _native_camera_enrollment(value: Any, generic: Any) -> dict[str, Any] | None:
    """Validate cached native metadata and its current generic-review linkage.

    This is a display boundary, not a native identity evaluator or a persistent
    camera binding. No provider, endpoint lookup or filesystem access occurs.
    """

    def exact(item: Any, keys: set[str]) -> bool:
        return type(item) is dict and set(item) == keys

    def text_value(item: Any, maximum: int = 1024) -> bool:
        return (
            type(item) is str
            and bool(item)
            and all(
                ord(char) >= 32
                and ord(char) != 127
                and not 0xD800 <= ord(char) <= 0xDFFF
                for char in item
            )
            and len(item.encode("utf-8")) <= maximum
        )

    def digest(item: Any) -> bool:
        return type(item) is str and re.fullmatch(r"[a-f0-9]{64}", item) is not None

    def codes(item: Any) -> bool:
        return (
            type(item) is list
            and len(item) <= 32
            and all(
                type(code) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code)
                for code in item
            )
            and len(set(item)) == len(item)
        )

    empty = ("PROVIDER_UNAVAILABLE", "NO_INVENTORY", "INVALIDATED")
    if not isinstance(value, dict) or not exact(
        value,
        {
            "schema",
            "status",
            "provenance",
            "inventory_sha256",
            "inventory_operation_id",
            "generic_candidate_sha256",
            "generic_report_sha256",
            "generic_operation_id",
            "candidates",
            "identity",
            "review",
            "blockers",
            "connected",
            "qualified",
            "persistent_binding",
            "physical_authority",
            "invalidation_reason",
        },
    ):
        return None
    if (
        value["schema"] != "rocell.wizard_native_camera_enrollment.v1"
        or value["status"]
        not in (
            *empty,
            "ENDPOINT_CHOICES_AVAILABLE",
            "IDENTITY_RETAINED",
            "ENDPOINT_METADATA_REVIEWED",
            "REVIEW_HELD",
        )
        or any(
            value[key] is not False
            for key in (
                "connected",
                "qualified",
                "persistent_binding",
                "physical_authority",
            )
        )
        or not exact(
            value["provenance"],
            {
                "mode",
                "session_id",
                "source_sha256",
                "provider_provenance",
                "helper_sha256",
                "scope",
            },
        )
        or not codes(value["blockers"])
        or not (
            value["invalidation_reason"] is None
            or text_value(value["invalidation_reason"], 512)
        )
        or type(value["candidates"]) is not list
        or len(value["candidates"]) > 128
    ):
        return None
    origin = value["provenance"]
    if (
        origin["mode"] not in ("rehearsal", "physical")
        or not text_value(origin["session_id"], 2048)
        or not digest(origin["source_sha256"])
        or origin["scope"] != "NATIVE_ENDPOINT_METADATA_ONLY"
        or origin["provider_provenance"]
        not in (None, "INCAPABLE_FIXTURE", "WINDOWS_NATIVE_METADATA")
        or not (origin["helper_sha256"] is None or digest(origin["helper_sha256"]))
        or (
            (origin["provider_provenance"] is None) != (origin["helper_sha256"] is None)
        )
    ):
        return None
    ids: set[str] = set()
    for row in value["candidates"]:
        if (
            not exact(row, {"choice_id", "friendly_name", "endpoint_sha256"})
            or not text_value(row["choice_id"], 128)
            or row["choice_id"] in ids
            or not text_value(row["friendly_name"])
            or not digest(row["endpoint_sha256"])
        ):
            return None
        ids.add(row["choice_id"])
    if value["status"] in empty:
        if (
            value["candidates"]
            or value["identity"] is not None
            or value["review"] is not None
            or any(
                value[key] is not None
                for key in (
                    "inventory_sha256",
                    "inventory_operation_id",
                    "generic_candidate_sha256",
                    "generic_report_sha256",
                    "generic_operation_id",
                )
            )
            or (
                value["status"] == "PROVIDER_UNAVAILABLE"
                and origin["provider_provenance"] is not None
            )
        ):
            return None
        return value
    current = _device_metadata(generic)
    if current is None:
        return None
    camera_review = current["devices"]["CAMERA"]["review"]
    if (
        camera_review is None
        or origin["provider_provenance"] is None
        or any(
            origin[key] != current["provenance"][key]
            for key in ("mode", "session_id", "source_sha256")
        )
        or not digest(value["inventory_sha256"])
        or not text_value(value["inventory_operation_id"], 128)
        or value["generic_candidate_sha256"] != camera_review["candidate_sha256"]
        or value["generic_report_sha256"] != camera_review["report_sha256"]
        or value["generic_operation_id"] != camera_review["operation_id"]
    ):
        return None
    identity = value["identity"]
    if identity is not None and (
        not exact(
            identity,
            {
                "choice_id",
                "endpoint_sha256",
                "identity_sha256",
                "operation_id",
                "exact_endpoint_observed",
                "generic_device_match",
                "container_match",
                "blockers",
            },
        )
        or not any(
            row["choice_id"] == identity["choice_id"]
            and row["endpoint_sha256"] == identity["endpoint_sha256"]
            for row in value["candidates"]
        )
        or not digest(identity["identity_sha256"])
        or not text_value(identity["operation_id"], 128)
        or not codes(identity["blockers"])
        or any(
            type(identity[key]) is not bool
            for key in (
                "exact_endpoint_observed",
                "generic_device_match",
                "container_match",
            )
        )
    ):
        return None
    if value["status"] == "ENDPOINT_CHOICES_AVAILABLE":
        return value if identity is None and value["review"] is None else None
    if identity is None:
        return None
    if value["status"] == "IDENTITY_RETAINED":
        return value if value["review"] is None else None
    review = value["review"]
    if (
        not exact(
            review,
            {
                "choice_id",
                "reviewer_id",
                "binding_sha256",
                "status",
                "physical_authority",
            },
        )
        or review["physical_authority"] is not False
        or review["choice_id"] != identity["choice_id"]
        or not text_value(review["reviewer_id"], 2048)
    ):
        return None
    if value["status"] == "ENDPOINT_METADATA_REVIEWED":
        return (
            value
            if (
                review["status"] == "REVIEWED_ENDPOINT_METADATA_ONLY"
                and digest(review["binding_sha256"])
                and all(
                    identity[key] is True
                    for key in (
                        "exact_endpoint_observed",
                        "generic_device_match",
                        "container_match",
                    )
                )
                and not identity["blockers"]
            )
            else None
        )
    return (
        value
        if review["status"] == "METADATA_ACKNOWLEDGED_BUT_HELD"
        and review["binding_sha256"] is None
        else None
    )


def _camera_helper_registration(value: Any) -> dict[str, Any] | None:
    """Check only a bounded cached projection; never inspect or register files."""

    def exact(item: Any, keys: set[str]) -> bool:
        return type(item) is dict and set(item) == keys

    def text_value(item: Any, maximum: int = 128) -> bool:
        return (
            type(item) is str
            and bool(item)
            and all(
                ord(char) >= 32
                and ord(char) != 127
                and not 0xD800 <= ord(char) <= 0xDFFF
                for char in item
            )
            and len(item.encode("utf-8")) <= maximum
        )

    def digest(item: Any) -> bool:
        return type(item) is str and re.fullmatch(r"[a-f0-9]{64}", item) is not None

    def codes(item: Any) -> bool:
        return (
            type(item) is list
            and len(item) <= 32
            and all(
                type(code) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code)
                for code in item
            )
            and len(set(item)) == len(item)
        )

    if not isinstance(value, dict) or not exact(
        value,
        {
            "schema",
            "status",
            "provenance",
            "inspection",
            "review",
            "blockers",
            "allowed_operations",
            "probe_allowed",
            "capture_allowed",
            "connected",
            "qualified",
            "physical_authority",
            "invalidation_reason",
        },
    ):
        return None
    if (
        value["schema"] != "rocell.wizard_camera_helper_registration.v1"
        or value["status"]
        not in (
            "NO_INSPECTION",
            "INSPECTION_RETAINED",
            "METADATA_HELPER_REGISTERED",
            "REVIEW_HELD",
            "INVALIDATED",
        )
        or any(
            value[key] is not False
            for key in (
                "probe_allowed",
                "capture_allowed",
                "connected",
                "qualified",
                "physical_authority",
            )
        )
        or type(value["allowed_operations"]) is not list
        or len(value["allowed_operations"]) != 2
        or "inventory" not in value["allowed_operations"]
        or "identity" not in value["allowed_operations"]
        or not codes(value["blockers"])
        or not (
            value["invalidation_reason"] is None
            or text_value(value["invalidation_reason"], 512)
        )
        or not exact(
            value["provenance"], {"mode", "session_id", "source_sha256", "scope"}
        )
    ):
        return None
    origin = value["provenance"]
    if (
        origin["mode"] not in ("rehearsal", "physical")
        or not text_value(origin["session_id"])
        or not digest(origin["source_sha256"])
        or origin["scope"] != "CAMERA_HELPER_METADATA_ONLY"
    ):
        return None
    if value["status"] in ("NO_INSPECTION", "INVALIDATED"):
        return (
            value if value["inspection"] is None and value["review"] is None else None
        )
    inspection = value["inspection"]
    if (
        not exact(
            inspection,
            {
                "catalog_id",
                "display_name",
                "catalog_sha256",
                "inspection_sha256",
                "operation_id",
                "operator_id",
                "inspection_status",
                "inspection_provenance",
                "helper_sha256",
                "eligible_for_metadata_registration",
                "blockers",
            },
        )
        or any(
            not text_value(inspection[key])
            for key in ("catalog_id", "display_name", "operation_id", "operator_id")
        )
        or not digest(inspection["catalog_sha256"])
        or not digest(inspection["inspection_sha256"])
        or not (
            inspection["helper_sha256"] is None or digest(inspection["helper_sha256"])
        )
        or type(inspection["eligible_for_metadata_registration"]) is not bool
        or not codes(inspection["blockers"])
        or inspection["inspection_status"]
        not in (
            "MATCHED_METADATA_CATALOG",
            "MISSING_FILES",
            "HASH_DRIFT",
            "UNSAFE_OR_UNREADABLE",
        )
        or inspection["inspection_provenance"]
        != (
            "INCAPABLE_FIXTURE"
            if origin["mode"] == "rehearsal"
            else "WORKSPACE_FILE_INSPECTION"
        )
    ):
        return None
    eligible = inspection["eligible_for_metadata_registration"]
    if eligible:
        if (
            inspection["inspection_status"] != "MATCHED_METADATA_CATALOG"
            or inspection["helper_sha256"] is None
        ):
            return None
    elif inspection["helper_sha256"] is not None:
        return None
    if value["status"] == "INSPECTION_RETAINED":
        return value if value["review"] is None else None
    review = value["review"]
    if (
        not exact(
            review,
            {
                "reviewer_id",
                "review_operation_id",
                "status",
                "registration_sha256",
                "distinct_operator_labels",
                "physical_authority",
            },
        )
        or not text_value(review["reviewer_id"])
        or not text_value(review["review_operation_id"])
        or review["reviewer_id"] == inspection["operator_id"]
        or review["distinct_operator_labels"] is not True
        or review["physical_authority"] is not False
    ):
        return None
    if value["status"] == "METADATA_HELPER_REGISTERED":
        return (
            value
            if eligible
            and review["status"] == "METADATA_ONLY_REGISTERED"
            and digest(review["registration_sha256"])
            else None
        )
    return (
        value
        if not eligible
        and review["status"] == "ACKNOWLEDGED_BUT_HELD"
        and review["registration_sha256"] is None
        else None
    )


def _arm_resolution(value: Any, owner: dict[str, Any]) -> dict[str, Any] | None:
    """Only the compact producer summary, never a raw trace parser/resolver."""
    v = _CameraConfigurationDisplay
    errors = {
        "REVIEWED_CONTROLLER_CHANGED",
        "CONTROLLER_RESOLUTION_CANCELLED",
        "CONTROLLER_RESOLUTION_DEADLINE_OR_CLOCK",
        "CONTROLLER_METADATA_NOT_FRESH",
        "CONTROLLER_METADATA_HELD",
        "INVALID_CONTROLLER_METADATA",
        "CONTROLLER_METADATA_BYTE_LIMIT",
        "CONTROLLER_METADATA_ACQUISITION_FAILED",
        "CONTROLLER_RESOLUTION_INTERRUPTED",
        "CM_PROPERTY_STRING_INVALID",
        "CM_PROPERTY_TYPE_OR_SIZE_INVALID",
        "CM_LIST_INVALID",
        "CM_LIST_AMBIGUOUS_OR_OVER_LIMIT",
        "CM_LIST_CHANGED",
    }
    limitations = [
        "METADATA_SNAPSHOT_NOT_ATOMIC_COM_TO_HANDLE_BINDING",
        "GENERIC_UNIT_SERIAL_NOT_USB_DESCRIPTOR_VERIFICATION",
        "ARM_MODEL_FIRMWARE_BOOT_AND_POWER_NOT_OBSERVED",
        "PHYSICAL_BACKEND_AND_RELEASE_REMAIN_HELD",
    ]
    if not (
        v.exact(
            value,
            {
                "schema",
                "trace_sha256",
                "reviewed_binding_sha256",
                "origin",
                "attempt_count",
                "attempts",
                "status",
                "physical_authority",
                "arm_connected",
                "qualified",
                "limitations",
            },
        )
        and value["schema"] == "rocell.arm_controller_resolution_trace_summary.v1"
        and v.digest(value["trace_sha256"])
        and v.digest(value["reviewed_binding_sha256"])
        and value["origin"]
        == (
            "SYNTHETIC_REHEARSAL"
            if owner["provenance"] == "INCAPABLE_NONPURGING_ARM_WORKER"
            else "PHYSICAL_OBSERVATION"
        )
        and all(
            value[key] is False
            for key in ("physical_authority", "arm_connected", "qualified")
        )
        and v.integer(value["attempt_count"], 0, 2)
        and type(value["attempts"]) is list
        and len(value["attempts"]) == value["attempt_count"]
        and value["limitations"] == limitations
        and (
            owner["native"] is None
            or value["reviewed_binding_sha256"]
            == owner["native"]["controller_binding_sha256"]
        )
    ):
        return None
    for index, row in enumerate(value["attempts"]):
        if not (
            v.exact(
                row,
                {
                    "phase",
                    "status",
                    "snapshot_sha256",
                    "resolution_sha256",
                    "error_code",
                },
            )
            and row["phase"] == ("PRE_OPEN", "PRE_WRITE")[index]
            and row["status"] in ("MATCHED_METADATA_ONLY", "HELD")
            and all(
                row[key] is None or v.digest(row[key])
                for key in ("snapshot_sha256", "resolution_sha256")
            )
            and (row["resolution_sha256"] is None or row["snapshot_sha256"] is not None)
            and (
                bool(row["snapshot_sha256"] and row["resolution_sha256"])
                and row["error_code"] is None
                if row["status"] == "MATCHED_METADATA_ONLY"
                else type(row["error_code"]) is str and row["error_code"] in errors
            )
            and (
                index == 0 or value["attempts"][0]["status"] == "MATCHED_METADATA_ONLY"
            )
        ):
            return None
    expected = (
        "NOT_ATTEMPTED"
        if not value["attempts"]
        else (
            "HELD"
            if any(row["status"] == "HELD" for row in value["attempts"])
            else (
                "PRE_OPEN_MATCHED"
                if len(value["attempts"]) == 1
                else "PRE_WRITE_MATCHED"
            )
        )
    )
    return value if value["status"] == expected else None


def _arm_process(value: Any) -> dict[str, Any] | None:
    """Closed cached presentation only; never import a process/native provider."""

    def exact(v: Any, keys: str) -> bool:
        return type(v) is dict and set(v) == set(keys.split())

    def text(v: Any, maximum: int = 128) -> bool:
        return (
            type(v) is str
            and 0 < len(v.encode("utf-8", errors="replace")) <= maximum
            and all(
                ord(c) >= 32 and ord(c) != 127 and not 0xD800 <= ord(c) <= 0xDFFF
                for c in v
            )
        )

    def digest(v: Any) -> bool:
        return type(v) is str and re.fullmatch(r"[a-f0-9]{64}", v) is not None

    def count(v: Any, maximum: int = 2**53 - 1) -> bool:
        return type(v) is int and 0 <= v <= maximum

    def codes(v: Any, maximum: int = 16) -> bool:
        return type(v) is list and len(v) <= maximum and all(text(x) for x in v)

    def held(v: dict[str, Any]) -> bool:
        return (
            all(
                v[k] is False
                for k in (
                    "physical_authority",
                    "arm_connected",
                    "device_cleanup_proven",
                )
            )
            and v["final_power_state"] == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
        )

    states = (
        "SUCCEEDED_DIAGNOSTIC",
        "BLOCKED_PRE_OPEN",
        "CANCELLED_PRE_OPEN",
        "FAILED_UNCERTAIN",
    )
    version_two = (
        type(value) is dict
        and value.get("schema") == "rocell.arm_owned_evidence_summary.v2"
    )
    if not exact(
        value,
        "schema status provenance session_id attempt_id source_sha256 permit_sha256 operation_sha256 selected_identity_sha256 worker_registration_sha256 request_sha256 inner_request_sha256 evidence_sha256 process handshake feedback native blockers physical_authority arm_connected device_cleanup_proven final_power_state meaning"
        + (" resolution" if version_two else ""),
    ):
        return None
    if (
        value["schema"]
        not in (
            "rocell.arm_owned_evidence_summary.v1",
            "rocell.arm_owned_evidence_summary.v2",
        )
        or value["status"]
        not in ("COMPLETE_INCAPABLE_EVIDENCE", "INCOMPLETE", "PHYSICAL_HELD")
        or value["provenance"]
        not in ("INCAPABLE_NONPURGING_ARM_WORKER", "PHYSICAL_NONPURGING_ARM_HELD")
        or not held(value)
        or not text(value["meaning"], 512)
        or not codes(value["blockers"])
        or not all(
            type(value[k]) is str
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}", value[k])
            for k in ("session_id", "attempt_id")
        )
        or not all(
            digest(value[k])
            for k in (
                "source_sha256",
                "permit_sha256",
                "operation_sha256",
                "selected_identity_sha256",
                "worker_registration_sha256",
                "request_sha256",
                "inner_request_sha256",
                "evidence_sha256",
            )
        )
    ):
        return None
    p, h, f, n = (value[k] for k in ("process", "handshake", "feedback", "native"))
    if (
        not exact(
            p,
            "status process_created initial_thread_resumed tree_exit_confirmed returncode primary_error cleanup_errors cleanup_error_count cleanup_errors_omitted stdin_bytes_written stdout_bytes stdout_sha256 stderr_bytes stderr_sha256",
        )
        or p["status"] not in ("SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT")
        or not all(
            type(p[k]) is bool
            for k in (
                "process_created",
                "initial_thread_resumed",
                "tree_exit_confirmed",
            )
        )
        or (p["initial_thread_resumed"] and not p["process_created"])
        or not (p["returncode"] is None or count(p["returncode"], 2**32 - 1))
        or not (p["primary_error"] is None or text(p["primary_error"]))
        or not codes(p["cleanup_errors"])
        or not all(
            count(p[k])
            for k in (
                "cleanup_error_count",
                "cleanup_errors_omitted",
                "stdin_bytes_written",
                "stdout_bytes",
                "stderr_bytes",
            )
        )
        or p["cleanup_error_count"]
        != len(p["cleanup_errors"]) + p["cleanup_errors_omitted"]
        or not digest(p["stdout_sha256"])
        or not digest(p["stderr_sha256"])
        or not exact(h, "ready_retained release_retained child_pid")
        or any(type(h[k]) is not bool for k in ("ready_retained", "release_retained"))
        or not (
            h["child_pid"] is None
            or (count(h["child_pid"], 2**32 - 1) and h["child_pid"] > 0)
        )
        or (h["release_retained"] and not h["ready_retained"])
    ):
        return None
    if f is not None and (
        not exact(
            f,
            "status technical_response_valid connection_closed response_bytes response_sha256 unexpected_bytes unexpected_sha256 unexpected_bytes_unretained",
        )
        or f["status"] not in states
        or any(
            type(f[k]) is not bool
            for k in ("technical_response_valid", "connection_closed")
        )
        or not all(
            count(f[k])
            for k in (
                "response_bytes",
                "unexpected_bytes",
                "unexpected_bytes_unretained",
            )
        )
        or not digest(f["response_sha256"])
        or not digest(f["unexpected_sha256"])
    ):
        return None
    if n is not None:

        def issue(v: Any) -> bool:
            return (
                exact(v, "code operation winerror")
                and type(v["code"]) is str
                and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", v["code"]) is not None
                and type(v["operation"]) is str
                and re.fullmatch(r"[a-z][a-z0-9_:]{0,63}", v["operation"]) is not None
                and count(v["winerror"], 2**32 - 1)
            )

        if (
            not exact(
                n,
                "schema evidence_sha256 request_sha256 controller_binding_sha256 worker_result_sha256 worker_status native_cleanup_confirmed resource_counts pending_io_unresolved startup_input_observed native_primary_error native_cleanup_errors late_read_bytes late_read_sha256 physical_authority arm_connected device_cleanup_proven final_power_state physical_hold meaning",
            )
            or n["schema"] != "rocell.arm_native_lifecycle_summary.v1"
            or not held(n)
            or n["worker_status"] not in states
            or not all(
                digest(n[k])
                for k in (
                    "evidence_sha256",
                    "request_sha256",
                    "controller_binding_sha256",
                    "worker_result_sha256",
                    "late_read_sha256",
                )
            )
            or not all(
                n[k] is None or type(n[k]) is bool
                for k in (
                    "native_cleanup_confirmed",
                    "pending_io_unresolved",
                    "startup_input_observed",
                )
            )
            or not (
                n["native_primary_error"] is None or issue(n["native_primary_error"])
            )
            or type(n["native_cleanup_errors"]) is not list
            or len(n["native_cleanup_errors"]) > 8
            or not all(issue(i) for i in n["native_cleanup_errors"])
            or not count(n["late_read_bytes"], 1024)
            or not text(n["physical_hold"], 512)
            or not text(n["meaning"], 512)
        ):
            return None
        r = n["resource_counts"]
        if r is not None and (
            not exact(r, "acquired close_attempted close_confirmed unresolved")
            or not all(count(i, 3) for i in r.values())
            or r["acquired"] != r["close_confirmed"] + r["unresolved"]
            or not r["close_confirmed"] <= r["close_attempted"] <= r["acquired"]
        ):
            return None
    if (
        version_two
        and value["resolution"] is not None
        and _arm_resolution(value["resolution"], value) is None
    ):
        return None
    if value["status"] == "COMPLETE_INCAPABLE_EVIDENCE" and (
        f is None
        or n is None
        or not h["ready_retained"]
        or not h["release_retained"]
        or (version_two and value["resolution"] is None)
        or value["provenance"] != "INCAPABLE_NONPURGING_ARM_WORKER"
    ):
        return None
    return value


def _camera_process(value: Any) -> dict[str, Any] | None:
    """Validate cached display data only, without provider or artifact I/O."""

    def exact(item: Any, keys: set[str]) -> bool:
        return type(item) is dict and set(item) == keys

    def digest(item: Any) -> bool:
        return type(item) is str and re.fullmatch(r"[a-f0-9]{64}", item) is not None

    def identifier(item: Any) -> bool:
        return (
            type(item) is str
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", item) is not None
        )

    def count(item: Any, maximum: int = 9_007_199_254_740_991) -> bool:
        return type(item) is int and 0 <= item <= maximum

    def bounded_text(item: Any, maximum: int) -> bool:
        return (
            type(item) is str
            and bool(item)
            and not any(
                ord(character) < 32
                or ord(character) == 127
                or 0xD800 <= ord(character) <= 0xDFFF
                for character in item
            )
            and len(item.encode("utf-8")) <= maximum
        )

    def codes(item: Any) -> bool:
        return (
            type(item) is list
            and len(item) <= 16
            and all(
                type(code) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", code)
                for code in item
            )
        )

    if not (
        exact(
            value,
            {
                "schema",
                "status",
                "evidence_sha256",
                "binding",
                "process",
                "native",
                "capture",
                "blockers",
                "device_cleanup_proven",
                "physical_authority",
                "qualified",
                "meaning",
            },
        )
        and value["schema"] == "rocell.rehearsal_owned_camera_summary.v1"
        and value["status"]
        in ("RETAINED_COMPLETE_REHEARSAL", "RETAINED_INCOMPLETE_REHEARSAL")
        and digest(value["evidence_sha256"])
        and bounded_text(value["meaning"], 512)
        and codes(value["blockers"])
        and all(
            value[key] is False
            for key in ("device_cleanup_proven", "physical_authority", "qualified")
        )
        and exact(
            value["binding"],
            {
                "session_id",
                "attempt_id",
                "source_sha256",
                "permit_sha256",
                "operation_sha256",
                "selected_identity_sha256",
                "settings_epoch",
            },
        )
        and all(
            identifier(value["binding"][key]) for key in ("session_id", "attempt_id")
        )
        and all(
            digest(value["binding"][key])
            for key in (
                "source_sha256",
                "permit_sha256",
                "operation_sha256",
                "selected_identity_sha256",
                "settings_epoch",
            )
        )
    ):
        return None
    process, native, capture = value["process"], value["native"], value["capture"]
    if process is not None and not (
        exact(
            process,
            {
                "status",
                "created",
                "resumed",
                "tree_exit_confirmed",
                "cleanup_errors",
                "cleanup_error_count",
                "cleanup_errors_omitted",
                "primary_error",
                "returncode",
                "stdout_bytes",
                "stderr_bytes",
                "request_sha256",
            },
        )
        and process["status"] in ("SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT")
        and all(
            type(process[key]) is bool
            for key in ("created", "resumed", "tree_exit_confirmed")
        )
        and type(process["cleanup_errors"]) is list
        and len(process["cleanup_errors"]) <= 16
        and all(bounded_text(code, 128) for code in process["cleanup_errors"])
        and count(process["cleanup_error_count"])
        and count(process["cleanup_errors_omitted"])
        and process["cleanup_error_count"]
        == len(process["cleanup_errors"]) + process["cleanup_errors_omitted"]
        and (
            process["primary_error"] is None
            or bounded_text(process["primary_error"], 128)
        )
        and (
            process["returncode"] is None
            or (
                type(process["returncode"]) is int
                and -(2**31) <= process["returncode"] <= 2**32 - 1
            )
        )
        and count(process["stdout_bytes"], 32768)
        and count(process["stderr_bytes"], 8192)
        and digest(process["request_sha256"])
        and (not process["resumed"] or process["created"])
    ):
        return None
    native_bounds = {
        "source_activation_attempts": 1,
        "source_opened": 1,
        "source_shutdown_attempts": 1,
        "control_set_attempts": 6,
        "samples_received": 100000,
        "frames_written": 32,
    }
    if native is not None and not (
        exact(
            native,
            {"receipt_valid", "status", "cleanup_confirmed", "counts", "frame_count"},
        )
        and all(
            type(native[key]) is bool for key in ("receipt_valid", "cleanup_confirmed")
        )
        and native["status"] in ("OK", "FAILED")
        and exact(native["counts"], set(native_bounds))
        and all(
            count(native["counts"][key], maximum)
            for key, maximum in native_bounds.items()
        )
        and count(native["frame_count"], 32)
    ):
        return None
    if capture is not None and not (
        exact(
            capture,
            {
                "metadata_binding_valid",
                "manifest_sha256",
                "plan_sha256",
                "envelope_sha256",
                "source_contract_sha256",
                "frames",
                "logical_bytes",
            },
        )
        and type(capture["metadata_binding_valid"]) is bool
        and all(
            digest(capture[key])
            for key in (
                "manifest_sha256",
                "plan_sha256",
                "envelope_sha256",
                "source_contract_sha256",
            )
        )
        and count(capture["frames"], 32)
        and count(capture["logical_bytes"])
    ):
        return None
    if value["status"] == "RETAINED_COMPLETE_REHEARSAL" and not (
        process is not None
        and process["status"] == "SUCCEEDED"
        and process["created"]
        and process["resumed"]
        and process["tree_exit_confirmed"]
        and process["primary_error"] is None
        and process["cleanup_error_count"] == 0
        and process["returncode"] == 0
        and native is not None
        and native["receipt_valid"]
        and native["status"] == "OK"
        and native["cleanup_confirmed"]
        and native["frame_count"] >= 1
        and capture is not None
        and capture["metadata_binding_valid"]
        and capture["frames"] == native["frame_count"]
        and capture["logical_bytes"] >= 1
        and not value["blockers"]
    ):
        return None
    return value


class _CameraConfigurationDisplay:
    """Pure bounded display validation; no probe, staging or driver calls."""

    IDS = ("exposure", "gain", "white_balance", "brightness", "contrast", "saturation")

    @staticmethod
    def exact(value: Any, keys: set[str]) -> bool:
        return type(value) is dict and set(value) == keys

    @staticmethod
    def digest(value: Any) -> bool:
        return type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value) is not None

    @staticmethod
    def identifier(value: Any) -> bool:
        return (
            type(value) is str
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}", value) is not None
        )

    @staticmethod
    def string(value: Any, limit: int) -> bool:
        return (
            type(value) is str
            and bool(value)
            and not any(
                ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF
                for char in value
            )
            and len(value.encode("utf-8")) <= limit
        )

    @staticmethod
    def integer(value: Any, low: int = -(2**31), high: int = 2**31 - 1) -> bool:
        return type(value) is int and low <= value <= high

    @classmethod
    def mode(cls, value: Any) -> bool:
        return (
            cls.exact(
                value,
                {
                    "width",
                    "height",
                    "fps_numerator",
                    "fps_denominator",
                    "subtype",
                    "stride_bytes",
                },
            )
            and all(cls.integer(value[key], 1, 16384) for key in ("width", "height"))
            and all(
                cls.integer(value[key], 1, 1000000)
                for key in ("fps_numerator", "fps_denominator")
            )
            and cls.string(value["subtype"], 64)
            and (
                value["stride_bytes"] is None
                or (
                    cls.integer(value["stride_bytes"], -1048576, 1048576)
                    and value["stride_bytes"] != 0
                )
            )
        )

    @classmethod
    def observation(cls, value: Any) -> bool:
        return (
            cls.exact(
                value,
                {
                    "control_id",
                    "minimum",
                    "maximum",
                    "step",
                    "default",
                    "capability_flags",
                    "value",
                    "flags",
                    "unit",
                },
            )
            and value["control_id"] in cls.IDS
            and all(
                cls.integer(value[key])
                for key in ("minimum", "maximum", "default", "value")
            )
            and cls.integer(value["step"], 1)
            and cls.integer(value["capability_flags"], 1, 3)
            and cls.integer(value["flags"], 1, 3)
            and value["minimum"] <= value["default"] <= value["maximum"]
            and value["minimum"] <= value["value"] <= value["maximum"]
            and cls.string(value["unit"], 64)
        )

    @classmethod
    def requested(cls, value: Any) -> bool:
        return (
            cls.exact(value, {"control_id", "value", "mode"})
            and value["control_id"] in cls.IDS
            and cls.integer(value["value"])
            and value["mode"] in ("auto", "manual")
        )

    @staticmethod
    def no_authority(value: dict[str, Any]) -> bool:
        return value["physical_authority"] is False and value["qualified"] is False

    @classmethod
    def binding(cls, value: Any) -> bool:
        return (
            cls.exact(
                value,
                {
                    "session_id",
                    "attempt_id",
                    "source_sha256",
                    "permit_sha256",
                    "operation_sha256",
                    "selected_identity_sha256",
                },
            )
            and cls.identifier(value["session_id"])
            and cls.identifier(value["attempt_id"])
            and all(
                cls.digest(value[key])
                for key in (
                    "source_sha256",
                    "permit_sha256",
                    "operation_sha256",
                    "selected_identity_sha256",
                )
            )
        )

    @staticmethod
    def choice(value: Any) -> bool:
        return (
            type(value) is str and re.fullmatch(r"mode-[a-f0-9]{24}", value) is not None
        )

    @classmethod
    def capabilities(cls, value: Any) -> dict[str, Any] | None:
        if not (
            cls.exact(
                value,
                {
                    "schema",
                    "status",
                    "capabilities_sha256",
                    "probe_evidence_sha256",
                    "binding",
                    "endpoint_sha256",
                    "modes",
                    "controls",
                    "unavailable_controls",
                    "physical_authority",
                    "qualified",
                    "meaning",
                },
            )
            and value["schema"] == "rocell.camera_capabilities.v1"
            and value["status"] == "REPORTED_REHEARSAL_ONLY"
            and cls.no_authority(value)
            and all(
                cls.digest(value[key])
                for key in (
                    "capabilities_sha256",
                    "probe_evidence_sha256",
                    "endpoint_sha256",
                )
            )
            and cls.binding(value["binding"])
            and cls.string(value["meaning"], 512)
            and type(value["modes"]) is list
            and len(value["modes"]) <= 128
            and type(value["controls"]) is list
            and len(value["controls"]) <= 6
            and all(cls.observation(row) for row in value["controls"])
            and type(value["unavailable_controls"]) is list
            and len(value["unavailable_controls"]) <= 6
            and all(item in cls.IDS for item in value["unavailable_controls"])
        ):
            return None
        partition = [row["control_id"] for row in value["controls"]] + value[
            "unavailable_controls"
        ]
        if len(partition) != 6 or len(set(partition)) != 6:
            return None
        choices = set()
        holds = {
            "UNSUPPORTED_PIXEL_FORMAT",
            "ODD_YUY2_WIDTH",
            "FRAME_BUDGET_EXCEEDED",
            "INVALID_REPORTED_STRIDE",
        }
        for item in value["modes"]:
            if not (
                cls.exact(item, {"choice_id", "mode", "selectable", "blockers"})
                and cls.choice(item["choice_id"])
                and cls.mode(item["mode"])
                and type(item["selectable"]) is bool
                and type(item["blockers"]) is list
                and len(item["blockers"]) <= 4
                and all(
                    type(code) is str and code in holds for code in item["blockers"]
                )
                and len(set(item["blockers"])) == len(item["blockers"])
                and item["selectable"] is (not item["blockers"])
                and (
                    not item["selectable"]
                    or (
                        item["mode"]["subtype"] == "YUY2"
                        and item["mode"]["width"] % 2 == 0
                    )
                )
            ):
                return None
            if item["choice_id"] in choices:
                return None
            choices.add(item["choice_id"])
            reported = item["mode"]
            expected = []
            if reported["subtype"] != "YUY2":
                expected.append("UNSUPPORTED_PIXEL_FORMAT")
            if reported["width"] % 2:
                expected.append("ODD_YUY2_WIDTH")
            if reported["width"] * reported["height"] * 2 > 64 * 1024 * 1024:
                expected.append("FRAME_BUDGET_EXCEEDED")
            if reported["stride_bytes"] is not None:
                if abs(reported["stride_bytes"]) < reported["width"] * 2:
                    expected.append("INVALID_REPORTED_STRIDE")
                elif (
                    abs(reported["stride_bytes"]) * reported["height"]
                    > 64 * 1024 * 1024
                    and "FRAME_BUDGET_EXCEEDED" not in expected
                ):
                    expected.append("FRAME_BUDGET_EXCEEDED")
            if set(expected) != set(item["blockers"]):
                return None
        return value

    @classmethod
    def candidate(
        cls, value: Any, caps: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if not (
            caps is not None
            and cls.exact(
                value,
                {
                    "schema",
                    "status",
                    "settings_epoch",
                    "capabilities_sha256",
                    "probe_evidence_sha256",
                    "session_id",
                    "source_sha256",
                    "selected_identity_sha256",
                    "endpoint_sha256",
                    "mode_choice_id",
                    "mode",
                    "controls",
                    "applied",
                    "physical_authority",
                    "qualified",
                    "meaning",
                },
            )
            and value["schema"] == "rocell.camera_configuration.v1"
            and value["status"] == "STAGED_NOT_APPLIED_REHEARSAL"
            and value["applied"] is False
            and cls.no_authority(value)
            and cls.digest(value["settings_epoch"])
            and cls.string(value["meaning"], 512)
            and cls.choice(value["mode_choice_id"])
            and all(
                value[key] == caps[key]
                for key in (
                    "capabilities_sha256",
                    "probe_evidence_sha256",
                    "endpoint_sha256",
                )
            )
            and all(
                value[key] == caps["binding"][key]
                for key in ("session_id", "source_sha256", "selected_identity_sha256")
            )
            and type(value["controls"]) is list
            and len(value["controls"]) <= 6
            and all(cls.requested(item) for item in value["controls"])
            and len({item["control_id"] for item in value["controls"]})
            == len(value["controls"])
        ):
            return None
        assert caps is not None
        selected = next(
            (
                item
                for item in caps["modes"]
                if item["choice_id"] == value["mode_choice_id"]
            ),
            None,
        )
        if (
            selected is None
            or not selected["selectable"]
            or not cls.mode(value["mode"])
            or value["mode"] != selected["mode"]
        ):
            return None
        for item in value["controls"]:
            reported = next(
                (
                    row
                    for row in caps["controls"]
                    if row["control_id"] == item["control_id"]
                ),
                None,
            )
            flag = 1 if item["mode"] == "auto" else 2
            if (
                reported is None
                or not reported["capability_flags"] & flag
                or not reported["minimum"] <= item["value"] <= reported["maximum"]
                or (item["value"] - reported["minimum"]) % reported["step"] != 0
            ):
                return None
        return value

    @staticmethod
    def reasons(value: Any, allowed: tuple[str, ...]) -> bool:
        return (
            type(value) is list
            and len(value) <= len(allowed)
            and all(type(code) is str and code in allowed for code in value)
            and len(set(value)) == len(value)
        )

    @classmethod
    def probe(cls, value: Any) -> dict[str, Any] | None:
        if not (
            cls.exact(
                value,
                {
                    "schema",
                    "status",
                    "evidence_sha256",
                    "binding",
                    "process",
                    "native",
                    "blockers",
                    "device_cleanup_proven",
                    "physical_authority",
                    "qualified",
                    "meaning",
                },
            )
            and value["schema"] == "rocell.rehearsal_camera_probe_summary.v1"
            and value["status"]
            in ("COMPLETE_PROBE_REHEARSAL", "INCOMPLETE_PROBE_REHEARSAL")
            and cls.digest(value["evidence_sha256"])
            and cls.binding(value["binding"])
            and cls.no_authority(value)
            and value["device_cleanup_proven"] is False
            and cls.string(value["meaning"], 512)
            and type(value["blockers"]) is list
            and len(value["blockers"]) <= 16
            and all(
                type(code) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", code)
                for code in value["blockers"]
            )
        ):
            return None
        process, native = value["process"], value["native"]
        if process is not None and not (
            cls.exact(
                process,
                {
                    "status",
                    "created",
                    "resumed",
                    "tree_exit_confirmed",
                    "cleanup_errors",
                    "cleanup_error_count",
                    "cleanup_errors_omitted",
                    "primary_error",
                    "returncode",
                    "stdout_bytes",
                    "stderr_bytes",
                    "request_sha256",
                },
            )
            and process["status"] in ("SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT")
            and all(
                type(process[key]) is bool
                for key in ("created", "resumed", "tree_exit_confirmed")
            )
            and (not process["resumed"] or process["created"])
            and type(process["cleanup_errors"]) is list
            and len(process["cleanup_errors"]) <= 16
            and all(cls.string(item, 128) for item in process["cleanup_errors"])
            and cls.integer(process["cleanup_error_count"], 0, 2**53 - 1)
            and cls.integer(process["cleanup_errors_omitted"], 0, 2**53 - 1)
            and process["cleanup_error_count"]
            == len(process["cleanup_errors"]) + process["cleanup_errors_omitted"]
            and (
                process["primary_error"] is None
                or cls.string(process["primary_error"], 128)
            )
            and (
                process["returncode"] is None
                or cls.integer(process["returncode"], -(2**31), 2**32 - 1)
            )
            and cls.integer(process["stdout_bytes"], 0, 32768)
            and cls.integer(process["stderr_bytes"], 0, 8192)
            and cls.digest(process["request_sha256"])
        ):
            return None
        counts = {
            "source_activation_attempts",
            "source_opened",
            "source_shutdown_attempts",
            "control_set_attempts",
            "samples_received",
            "frames_written",
        }
        if native is not None and not (
            cls.exact(
                native,
                {
                    "receipt_valid",
                    "status",
                    "cleanup_confirmed",
                    "counts",
                    "mode_count",
                    "control_count",
                },
            )
            and type(native["receipt_valid"]) is bool
            and type(native["cleanup_confirmed"]) is bool
            and native["status"] in ("OK", "FAILED")
            and cls.exact(native["counts"], counts)
            and all(
                cls.integer(
                    native["counts"][key], 0, 1 if key.startswith("source_") else 0
                )
                for key in counts
            )
            and cls.integer(native["mode_count"], 0, 128)
            and cls.integer(native["control_count"], 0, 6)
        ):
            return None
        if value["status"] == "COMPLETE_PROBE_REHEARSAL" and not (
            process is not None
            and process["status"] == "SUCCEEDED"
            and process["created"]
            and process["resumed"]
            and process["tree_exit_confirmed"]
            and process["cleanup_error_count"] == 0
            and process["primary_error"] is None
            and process["returncode"] == 0
            and native is not None
            and native["receipt_valid"]
            and native["status"] == "OK"
            and native["cleanup_confirmed"]
            and all(
                native["counts"][key] == 1
                for key in (
                    "source_activation_attempts",
                    "source_opened",
                    "source_shutdown_attempts",
                )
            )
            and not value["blockers"]
        ):
            return None
        return value

    @classmethod
    def readback(
        cls, value: Any, config: dict[str, Any] | None, caps: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        top_reasons = (
            "CAPTURE_NOT_SUCCESSFULLY_CLOSED",
            "ENDPOINT_MISMATCH",
            "MODE_READBACK_MISMATCH",
            "CONTROL_READBACK_MISMATCH",
        )
        row_reasons = (
            "CONTROL_READBACK_MISSING",
            "CONTROL_MODE_READBACK_MISMATCH",
            "MANUAL_VALUE_READBACK_MISMATCH",
            "CONTROL_CAPABILITY_DRIFT",
        )
        if not (
            config is not None
            and caps is not None
            and cls.exact(
                value,
                {
                    "schema",
                    "status",
                    "settings_epoch",
                    "probe_evidence_sha256",
                    "source_sha256",
                    "selected_identity_sha256",
                    "native_receipt_sha256",
                    "requested_mode",
                    "observed_mode",
                    "mode_matched",
                    "controls",
                    "reasons",
                    "physical_authority",
                    "qualified",
                    "meaning",
                },
            )
            and value["schema"] == "rocell.camera_readback.v1"
            and value["status"]
            in ("REQUESTED_SETTINGS_OBSERVED_REHEARSAL", "READBACK_MISMATCH_REHEARSAL")
            and all(
                value[key] == config[key]
                for key in (
                    "settings_epoch",
                    "probe_evidence_sha256",
                    "source_sha256",
                    "selected_identity_sha256",
                )
            )
            and cls.digest(value["native_receipt_sha256"])
            and cls.mode(value["requested_mode"])
            and value["requested_mode"] == config["mode"]
            and (value["observed_mode"] is None or cls.mode(value["observed_mode"]))
            and type(value["mode_matched"]) is bool
            and cls.reasons(value["reasons"], top_reasons)
            and cls.no_authority(value)
            and cls.string(value["meaning"], 512)
            and type(value["controls"]) is list
            and len(value["controls"]) == len(config["controls"])
            and value["mode_matched"]
            is not ("MODE_READBACK_MISMATCH" in value["reasons"])
        ):
            return None
        assert config is not None
        assert caps is not None
        actual, wanted = value["observed_mode"], config["mode"]
        if value["mode_matched"] and not (
            actual is not None
            and all(
                actual[key] == wanted[key] for key in ("width", "height", "subtype")
            )
            and actual["fps_numerator"] * wanted["fps_denominator"]
            == wanted["fps_numerator"] * actual["fps_denominator"]
        ):
            return None
        for row, request in zip(value["controls"], config["controls"]):
            if not (
                cls.exact(
                    row, {"control_id", "requested", "observed", "matched", "reasons"}
                )
                and row["control_id"] == request["control_id"]
                and cls.exact(row["requested"], {"value", "mode"})
                and cls.integer(row["requested"]["value"])
                and row["requested"]["value"] == request["value"]
                and row["requested"]["mode"] == request["mode"]
                and type(row["matched"]) is bool
                and cls.reasons(row["reasons"], row_reasons)
                and row["matched"] is (not row["reasons"])
            ):
                return None
            observed = row["observed"]
            reported = next(
                (
                    item
                    for item in caps["controls"]
                    if item["control_id"] == row["control_id"]
                ),
                None,
            )
            if observed is None:
                if "CONTROL_READBACK_MISSING" not in row["reasons"]:
                    return None
            elif not (
                cls.exact(observed, {"value", "flags", "unit"})
                and cls.integer(observed["value"])
                and cls.integer(observed["flags"], 1, 3)
                and cls.string(observed["unit"], 64)
                and "CONTROL_READBACK_MISSING" not in row["reasons"]
                and (observed["flags"] != (1 if request["mode"] == "auto" else 2))
                == ("CONTROL_MODE_READBACK_MISMATCH" in row["reasons"])
                and (
                    request["mode"] == "manual"
                    and observed["value"] != request["value"]
                )
                == ("MANUAL_VALUE_READBACK_MISMATCH" in row["reasons"])
                and (
                    "CONTROL_CAPABILITY_DRIFT" in row["reasons"]
                    or (
                        reported is not None
                        and observed["unit"] == reported["unit"]
                        and reported["minimum"]
                        <= observed["value"]
                        <= reported["maximum"]
                    )
                )
            ):
                return None
        if any(not row["matched"] for row in value["controls"]) != (
            "CONTROL_READBACK_MISMATCH" in value["reasons"]
        ) or (value["status"] == "REQUESTED_SETTINGS_OBSERVED_REHEARSAL") != (
            not value["reasons"]
        ):
            return None
        return value

    @classmethod
    def configuration(cls, value: Any) -> dict[str, Any] | None:
        if not (
            cls.exact(
                value,
                {
                    "schema",
                    "status",
                    "probe",
                    "capabilities",
                    "candidate",
                    "readback",
                    "physical_authority",
                    "qualified",
                    "meaning",
                },
            )
            and value["schema"] == "rocell.wizard_camera_configuration.v1"
            and value["status"]
            in ("PROBE_COMPLETE", "CONFIGURATION_STAGED", "READBACK_COMPLETE", "HELD")
            and cls.no_authority(value)
            and cls.string(value["meaning"], 512)
        ):
            return None
        probe = cls.probe(value["probe"])
        caps = (
            None
            if value["capabilities"] is None
            else cls.capabilities(value["capabilities"])
        )
        if probe is None or (value["capabilities"] is not None and caps is None):
            return None
        if caps is not None and not (
            probe["status"] == "COMPLETE_PROBE_REHEARSAL"
            and probe["evidence_sha256"] == caps["probe_evidence_sha256"]
            and probe["binding"] == caps["binding"]
            and probe["native"]["mode_count"] == len(caps["modes"])
            and probe["native"]["control_count"] == len(caps["controls"])
        ):
            return None
        candidate = (
            None
            if value["candidate"] is None
            else cls.candidate(value["candidate"], caps)
        )
        readback = (
            None
            if value["readback"] is None
            else cls.readback(value["readback"], candidate, caps)
        )
        if (value["candidate"] is not None and candidate is None) or (
            value["readback"] is not None and readback is None
        ):
            return None
        if (
            (
                value["status"] == "PROBE_COMPLETE"
                and (caps is None or candidate is not None or readback is not None)
            )
            or (
                value["status"] == "CONFIGURATION_STAGED"
                and (candidate is None or readback is not None)
            )
            or (
                value["status"] == "READBACK_COMPLETE"
                and (
                    readback is None
                    or readback["status"] != "REQUESTED_SETTINGS_OBSERVED_REHEARSAL"
                )
            )
        ):
            return None
        return value


def _camera_fault(value: Any) -> dict[str, Any] | None:
    """Closed diagnostic sidecar, never an exception-string classification."""
    v = _CameraConfigurationDisplay
    categories = {
        "NONE": (None, "NONE"),
        "CONTROL_READBACK_MISMATCH_REPORTED": (
            "INVALID_CAMERA_CONTRACT",
            "RETAINED_CALLER_ERROR_EXACT_MATCH",
        ),
        "PROCESS_CLEANUP_UNCONFIRMED": (None, "RETAINED_PROCESS_STATUS"),
        "OPERATION_CANCELLED": ("CANCELLED", "RETAINED_PROCESS_STATUS"),
        "OPERATION_TIMED_OUT": ("TIMED_OUT", "RETAINED_PROCESS_STATUS"),
        "UNCLASSIFIED_CALLER_ERROR": ("UNCLASSIFIED", "RETAINED_VALIDATION_HOLD"),
        "PROCESS_EXECUTION_UNCONFIRMED": (None, "RETAINED_PROCESS_STATUS"),
        "REQUEST_OR_PROCESS_EVIDENCE_UNAVAILABLE": (None, "RETAINED_VALIDATION_HOLD"),
        "NATIVE_EVIDENCE_UNVERIFIED": (None, "RETAINED_VALIDATION_HOLD"),
        "CAPTURE_RETENTION_UNVERIFIED": (None, "RETAINED_VALIDATION_HOLD"),
    }
    if not (
        v.exact(
            value,
            {
                "schema",
                "status",
                "evidence_sha256",
                "reason_category",
                "reported_code",
                "basis",
                "reason",
                "next_investigation",
                "retry_this_attempt_allowed",
                "automatic_retry_allowed",
                "clear_quarantine_allowed",
                "physical_authority",
                "qualified",
                "meaning",
            },
        )
        and value["schema"] == "rocell.camera_fault_diagnostic.v1"
        and v.digest(value["evidence_sha256"])
        and type(value["reason_category"]) is str
        and value["reason_category"] in categories
        and all(
            v.string(value[key], 512)
            for key in ("reason", "next_investigation", "meaning")
        )
        and all(
            value[key] is False
            for key in (
                "retry_this_attempt_allowed",
                "automatic_retry_allowed",
                "clear_quarantine_allowed",
                "physical_authority",
                "qualified",
            )
        )
    ):
        return None
    expected = categories[value["reason_category"]]
    return (
        value
        if (
            (value["reported_code"], value["basis"]) == expected
            and value["status"]
            == (
                "NO_REPORTED_FAULT"
                if value["reason_category"] == "NONE"
                else "FAULT_REPORTED"
            )
        )
        else None
    )


class _PhysicalCameraRuntimeDisplay(_CameraConfigurationDisplay):
    """Strict cached file-summary presentation, never inspection/admission."""

    FLAGS = (
        "dispatch_enabled",
        "driver_qualified",
        "hardware_qualified",
        "connected",
        "physical_authority",
    )
    PATHS = frozenset(
        "software/native/windows_camera/" + path
        for path in (
            "CMakeLists.txt",
            "camera_worker.cpp",
            "identity_metadata.cpp",
            "identity_metadata.h",
            "admission_entry.cpp",
            "admission_entry.h",
            "admission_entry_tests.cpp",
            "admission_protocol.cpp",
            "admission_protocol.h",
            "admission_protocol_tests.cpp",
            "capture_admission_entry.cpp",
            "capture_admission_entry.h",
            "capture_admission_entry_tests.cpp",
            "capture_admission_protocol.cpp",
            "capture_admission_protocol.h",
            "capture_admission_protocol_tests.cpp",
            "capture/CMakeLists.txt",
            "capture/admission_entry_wire_test.py",
            "owned_build_manifest.json",
            "owned_capture_build_manifest.json",
            "build-owned/Release/rocell_windows_camera.exe",
            "build-owned/Release/rocell_camera_admission_tests.exe",
            "build-owned/Release/rocell_camera_admission_entry_tests.exe",
            "build-owned-capture/Release/rocell_windows_camera.exe",
            "build-owned-capture/Release/rocell_windows_camera_probe_compile_check.exe",
            "build-owned-capture/Release/rocell_camera_capture_admission_tests.exe",
            "build-owned-capture/Release/rocell_camera_capture_admission_entry_tests.exe",
        )
    )
    REASONS = frozenset(
        (
            "MISSING",
            "UNREADABLE",
            "UNSAFE_PATH",
            "SIZE_LIMIT",
            "CHANGED_DURING_READ",
            "NOT_INSPECTED",
            "HASH_MISMATCH",
            "LENGTH_MISMATCH",
            "MANIFEST_INVALID",
            "MANIFEST_UNVERIFIED",
        )
    )

    @classmethod
    def label(cls, value: Any) -> bool:
        return (
            type(value) is str
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value) is not None
        )

    @classmethod
    def summary(cls, value: Any) -> bool:
        if not (
            cls.exact(
                value,
                {
                    "schema",
                    "operator_id",
                    "source_sha256",
                    "launch_session_id",
                    "report_sha256",
                    "status",
                    "purposes",
                    "coverage",
                    *cls.FLAGS,
                },
            )
            and value["schema"]
            == "rocell.physical_camera_runtime_inspection_summary.v1"
            and all(value[key] is False for key in cls.FLAGS)
            and cls.label(value["operator_id"])
            and cls.digest(value["source_sha256"])
            and cls.digest(value["report_sha256"])
            and type(value["launch_session_id"]) is str
            and re.fullmatch(r"wizard-[0-9a-f]{32}", value["launch_session_id"])
            is not None
            and value["status"] in ("FILES_MATCHED", "HELD")
            and cls.exact(value["purposes"], {"probe", "capture"})
            and cls.exact(
                value["coverage"],
                {"planned_paths", "observed_paths", "unobserved_paths"},
            )
            and all(cls.integer(n, 0, 40) for n in value["coverage"].values())
            and value["coverage"]["planned_paths"]
            == value["coverage"]["observed_paths"]
            + value["coverage"]["unobserved_paths"]
        ):
            return False
        for purpose, row in value["purposes"].items():
            pin = ("MATCHED", "HASH_MISMATCH", "LENGTH_MISMATCH", "NOT_OBSERVED")
            if not (
                cls.exact(
                    row,
                    {
                        "purpose",
                        "binary_status",
                        "build_status",
                        "source_status",
                        "artifact_status",
                        "source_counts",
                        "artifact_counts",
                        "gaps",
                    },
                )
                and row["purpose"] == purpose
                and row["binary_status"] in pin
                and row["build_status"] in (*pin, "MANIFEST_INVALID")
                and type(row["gaps"]) is list
                and len(row["gaps"]) <= 40
            ):
                return False
            for kind in ("source", "artifact"):
                counts, status = row[kind + "_counts"], row[kind + "_status"]
                if not (
                    cls.exact(counts, {"total", "matched", "gaps", "unverified"})
                    and all(cls.integer(n, 0, 40) for n in counts.values())
                    and counts["total"]
                    == counts["matched"] + counts["gaps"] + counts["unverified"]
                    and status in ("MATCHED", "GAPS", "NOT_VERIFIED")
                ):
                    return False
                if (
                    (status == "MATCHED" and counts["matched"] != counts["total"])
                    or (
                        status == "GAPS"
                        and (counts["gaps"] == 0 or counts["unverified"] != 0)
                    )
                    or (
                        status == "NOT_VERIFIED"
                        and counts["unverified"] != counts["total"]
                    )
                ):
                    return False
            pairs = set()
            for gap in row["gaps"]:
                if not (
                    cls.exact(gap, {"relative_path", "reason"})
                    and type(gap["relative_path"]) is str
                    and gap["relative_path"] in cls.PATHS
                    and type(gap["reason"]) is str
                    and gap["reason"] in cls.REASONS
                ):
                    return False
                pair = (gap["relative_path"], gap["reason"])
                if pair in pairs:
                    return False
                pairs.add(pair)
            if value["status"] == "FILES_MATCHED" and (
                any(
                    row[key] != "MATCHED"
                    for key in (
                        "binary_status",
                        "build_status",
                        "source_status",
                        "artifact_status",
                    )
                )
                or row["gaps"]
            ):
                return False
        return not (
            value["status"] == "FILES_MATCHED"
            and value["coverage"]["unobserved_paths"] != 0
        )

    @classmethod
    def projection(
        cls, value: Any, source: str, launch: str | None = None
    ) -> dict[str, Any] | None:
        if not (
            cls.exact(
                value,
                {
                    "schema",
                    "status",
                    "inspection",
                    "review",
                    "publication",
                    *cls.FLAGS,
                    "meaning",
                },
            )
            and value["schema"] == "rocell.wizard_physical_camera_runtime_review.v1"
            and all(value[key] is False for key in cls.FLAGS)
            and cls.string(value["meaning"], 512)
            and value["status"]
            in (
                "NOT_INSPECTED",
                "INSPECTION_RETAINED",
                "REVIEW_RECORDED",
                "HISTORICAL_HELD",
            )
            and cls.exact(value["publication"], {"status", "operation_id"})
            and value["publication"]["status"]
            in ("NOT_PUBLISHED", "PENDING", "CURRENT", "HISTORICAL_HELD")
            and (
                value["publication"]["operation_id"] is None
                or cls.identifier(value["publication"]["operation_id"])
            )
        ):
            return None
        observed, review, publication = (
            value["inspection"],
            value["review"],
            value["publication"]["status"],
        )
        if (
            (value["status"] == "HISTORICAL_HELD") != (publication == "HISTORICAL_HELD")
            or (
                publication == "CURRENT"
                and value["publication"]["operation_id"] is None
            )
            or (publication == "PENDING" and review is not None)
            or (
                value["status"] == "NOT_INSPECTED"
                and (
                    observed is not None
                    or review is not None
                    or publication not in ("NOT_PUBLISHED", "PENDING")
                )
            )
            or (
                value["status"] == "INSPECTION_RETAINED"
                and (
                    observed is None
                    or review is not None
                    or publication not in ("PENDING", "CURRENT")
                )
            )
            or (
                value["status"] == "REVIEW_RECORDED"
                and (observed is None or review is None or publication != "CURRENT")
            )
        ):
            return None
        if observed is not None and (
            not cls.summary(observed)
            or (
                publication == "CURRENT"
                and (
                    observed["source_sha256"] != source
                    or (launch is not None and observed["launch_session_id"] != launch)
                )
            )
        ):
            return None
        if review is not None and not (
            observed is not None
            and cls.exact(
                review,
                {
                    "reviewer_id",
                    "review_operation_id",
                    "inspection_sha256",
                    "status",
                    "distinct_operator_labels",
                },
            )
            and cls.label(review["reviewer_id"])
            and review["reviewer_id"].casefold() != observed["operator_id"].casefold()
            and cls.identifier(review["review_operation_id"])
            and review["inspection_sha256"] == observed["report_sha256"]
            and review["distinct_operator_labels"] is True
            and (
                publication != "CURRENT"
                or review["review_operation_id"] == value["publication"]["operation_id"]
            )
            and review["status"]
            == (
                "ACKNOWLEDGED_FILE_MATCH"
                if observed["status"] == "FILES_MATCHED"
                else "ACKNOWLEDGED_HELD_REPORT"
            )
        ):
            return None
        return value


class _PhysicalCameraDisplay(_CameraConfigurationDisplay):
    """Separate physical-shaped presentation, without importing a provider.

    Shared neutral mode/range checks do not relabel a rehearsal receipt. This
    validator cannot qualify evidence, admit a runtime or verify image bytes.
    """

    BINDING = {
        "session_id",
        "attempt_id",
        "source_sha256",
        "operation_sha256",
        "permit_sha256",
        "selected_identity_sha256",
        "endpoint_sha256",
        "helper_sha256",
        "runtime_registration_sha256",
        "probe_preparation_sha256",
        "probe_evidence_sha256",
    }

    @staticmethod
    def codes(value: Any, maximum: int = 16) -> bool:
        return (
            type(value) is list
            and len(value) <= maximum
            and all(
                type(code) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code)
                for code in value
            )
            and len(set(value)) == len(value)
        )

    @classmethod
    def physical_binding(cls, value: Any, capture: bool = False) -> bool:
        keys = (
            cls.BINDING - {"probe_preparation_sha256", "probe_evidence_sha256"}
            if capture
            else cls.BINDING
        )
        return cls.exact(value, keys) and all(
            (
                cls.identifier(item)
                if key in ("session_id", "attempt_id")
                else cls.digest(item)
            )
            for key, item in value.items()
        )

    @classmethod
    def held(cls, value: dict[str, Any]) -> bool:
        return (
            value["provenance"] == "PHYSICAL_UNQUALIFIED"
            and value["physical_authority"] is False
            and value["hardware_qualified"] is False
            and cls.string(value["meaning"], 512)
        )

    @classmethod
    def physical_capabilities(cls, value: Any) -> dict[str, Any] | None:
        if not (
            cls.exact(
                value,
                {
                    "schema",
                    "provenance",
                    "status",
                    "binding",
                    "modes",
                    "controls",
                    "physical_authority",
                    "hardware_qualified",
                    "capabilities_sha256",
                    "unavailable_controls",
                    "meaning",
                },
            )
            and value["schema"] == "rocell.physical_camera_capabilities.v1"
            and value["status"] == "OBSERVED_NATIVE_UNQUALIFIED"
            and cls.held(value)
            and cls.physical_binding(value["binding"])
            and cls.digest(value["capabilities_sha256"])
            and type(value["modes"]) is list
            and len(value["modes"]) <= 128
            and type(value["controls"]) is list
            and len(value["controls"]) <= 6
            and all(cls.observation(row) for row in value["controls"])
            and type(value["unavailable_controls"]) is list
            and all(item in cls.IDS for item in value["unavailable_controls"])
        ):
            return None
        partition = [item["control_id"] for item in value["controls"]] + value[
            "unavailable_controls"
        ]
        if len(partition) != 6 or len(set(partition)) != 6:
            return None
        choices = []
        for row in value["modes"]:
            if not (
                cls.exact(row, {"choice_id", "mode", "selectable", "blockers"})
                and cls.choice(row["choice_id"])
                and cls.mode(row["mode"])
                and cls.codes(row["blockers"], 4)
                and type(row["selectable"]) is bool
            ):
                return None
            choices.append(row["choice_id"])
            mode, expected = row["mode"], []
            if mode["subtype"] != "YUY2":
                expected.append("UNSUPPORTED_PIXEL_FORMAT")
            if mode["width"] < 2 or mode["width"] % 2:
                expected.append("UNSUPPORTED_YUY2_WIDTH")
            span = mode["width"] * mode["height"] * 2
            if mode["stride_bytes"] is not None:
                if abs(mode["stride_bytes"]) < mode["width"] * 2:
                    expected.append("INVALID_REPORTED_STRIDE")
                span = max(
                    span,
                    (mode["height"] - 1) * abs(mode["stride_bytes"])
                    + mode["width"] * 2,
                )
            if span > 64 * 1024 * 1024:
                expected.append("FRAME_BUDGET_EXCEEDED")
            if row["blockers"] != expected or row["selectable"] is not (not expected):
                return None
        return value if len(set(choices)) == len(choices) else None

    @classmethod
    def physical_candidate(
        cls, value: Any, caps: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if not (
            caps
            and cls.exact(
                value,
                {
                    "schema",
                    "provenance",
                    "status",
                    "capabilities_sha256",
                    "binding",
                    "mode_choice_id",
                    "mode",
                    "controls",
                    "applied",
                    "physical_authority",
                    "hardware_qualified",
                    "settings_epoch",
                    "meaning",
                },
            )
            and value["schema"] == "rocell.physical_camera_configuration.v1"
            and value["status"] == "STAGED_NOT_APPLIED_NATIVE"
            and cls.held(value)
            and value["applied"] is False
            and cls.digest(value["settings_epoch"])
            and value["capabilities_sha256"] == caps["capabilities_sha256"]
            and cls.physical_binding(value["binding"])
            and value["binding"] == caps["binding"]
            and type(value["controls"]) is list
            and len(value["controls"]) <= 6
            and all(cls.requested(item) for item in value["controls"])
        ):
            return None
        mode = next(
            (
                row
                for row in caps["modes"]
                if row["choice_id"] == value["mode_choice_id"]
            ),
            None,
        )
        if (
            not mode
            or not mode["selectable"]
            or not cls.mode(value["mode"])
            or value["mode"] != mode["mode"]
        ):
            return None
        ids = []
        for item in value["controls"]:
            ids.append(item["control_id"])
            observed = next(
                (
                    row
                    for row in caps["controls"]
                    if row["control_id"] == item["control_id"]
                ),
                None,
            )
            flag = 1 if item["mode"] == "auto" else 2
            if (
                not observed
                or not (observed["capability_flags"] & flag)
                or not observed["minimum"] <= item["value"] <= observed["maximum"]
                or (item["value"] - observed["minimum"]) % observed["step"]
            ):
                return None
        return value if len(set(ids)) == len(ids) else None

    @classmethod
    def physical_readback(
        cls, value: Any, config: dict[str, Any] | None, caps: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        keys = {
            "schema",
            "provenance",
            "status",
            "settings_epoch",
            "capabilities_sha256",
            "probe_binding",
            "capture_binding",
            "capture_preparation_sha256",
            "capture_evidence_sha256",
            "capture_request_sha256",
            "native_receipt_valid",
            "native_status",
            "native_requested_mode",
            "requested_mode",
            "observed_mode",
            "mode_matched",
            "controls",
            "reasons",
            "process_status",
            "process_cleanup_confirmed",
            "native_cleanup_confirmed",
            "frame_content_verified",
            "physical_authority",
            "hardware_qualified",
            "final_power_state",
            "readback_sha256",
            "meaning",
        }
        if not (
            config
            and caps
            and cls.exact(value, keys)
            and value["schema"] == "rocell.physical_camera_readback.v1"
            and cls.held(value)
            and all(
                cls.digest(value[key])
                for key in (
                    "capture_preparation_sha256",
                    "capture_evidence_sha256",
                    "capture_request_sha256",
                    "readback_sha256",
                )
            )
            and value["settings_epoch"] == config["settings_epoch"]
            and value["capabilities_sha256"] == caps["capabilities_sha256"]
            and cls.physical_binding(value["probe_binding"])
            and value["probe_binding"] == caps["binding"]
            and cls.physical_binding(value["capture_binding"], True)
            and all(
                value["capture_binding"][key] == caps["binding"][key]
                for key in (
                    "session_id",
                    "source_sha256",
                    "selected_identity_sha256",
                    "endpoint_sha256",
                )
            )
            and all(
                type(value[key]) is bool
                for key in (
                    "native_receipt_valid",
                    "mode_matched",
                    "process_cleanup_confirmed",
                    "native_cleanup_confirmed",
                )
            )
            and value["native_status"] in (None, "OK", "FAILED")
            and value["native_receipt_valid"] is (value["native_status"] is not None)
            and value["process_status"]
            in (
                "HELD",
                "CANCELLED",
                "TIMED_OUT",
                "FAILED",
                "SUCCEEDED_NATIVE_DIAGNOSTIC",
            )
            and value["frame_content_verified"] is False
            and value["final_power_state"] == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
            and cls.mode(value["requested_mode"])
            and value["requested_mode"] == config["mode"]
            and all(
                value[key] is None or cls.mode(value[key])
                for key in ("native_requested_mode", "observed_mode")
            )
            and cls.codes(value["reasons"])
            and type(value["controls"]) is list
            and len(value["controls"]) == len(config["controls"])
        ):
            return None
        expected = []
        if value["process_status"] != "SUCCEEDED_NATIVE_DIAGNOSTIC":
            expected.append("CAPTURE_CAMPAIGN_NOT_SUCCESSFUL")
        if not value["process_cleanup_confirmed"]:
            expected.append("PROCESS_CLEANUP_UNCONFIRMED")
        if not value["native_receipt_valid"]:
            expected.append("NATIVE_RECEIPT_UNAVAILABLE")
        elif value["native_status"] != "OK":
            expected.append("NATIVE_CAPTURE_FAILED")
        if not value["native_cleanup_confirmed"]:
            expected.append("NATIVE_CLEANUP_UNCONFIRMED")
        if not value["mode_matched"]:
            expected.append("MODE_READBACK_MISMATCH")
        if value["mode_matched"] and not (
            value["native_requested_mode"] == config["mode"]
            and value["observed_mode"] is not None
            and all(
                value["observed_mode"][key] == config["mode"][key]
                for key in ("width", "height", "subtype")
            )
            # Preserve fractions and mirror native same_format, without rounding.
            and value["observed_mode"]["fps_numerator"]
            * config["mode"]["fps_denominator"]
            == config["mode"]["fps_numerator"]
            * value["observed_mode"]["fps_denominator"]
            and (
                config["mode"]["stride_bytes"] is None
                or value["observed_mode"]["stride_bytes"]
                == config["mode"]["stride_bytes"]
            )
        ):
            return None
        for row, request in zip(value["controls"], config["controls"]):
            if not (
                cls.exact(
                    row, {"control_id", "requested", "observed", "matched", "reasons"}
                )
                and row["control_id"] == request["control_id"]
                and cls.exact(row["requested"], {"value", "mode"})
                and row["requested"]
                == {"value": request["value"], "mode": request["mode"]}
                and type(row["matched"]) is bool
                and cls.codes(row["reasons"], 4)
            ):
                return None
            failures, observed = [], row["observed"]
            pinned = next(
                item
                for item in caps["controls"]
                if item["control_id"] == row["control_id"]
            )
            if observed is None:
                failures.append("CONTROL_READBACK_MISSING")
            else:
                if (
                    not cls.observation(observed)
                    or observed["control_id"] != row["control_id"]
                ):
                    return None
                if observed["flags"] != (1 if request["mode"] == "auto" else 2):
                    failures.append("CONTROL_MODE_READBACK_MISMATCH")
                if (
                    request["mode"] == "manual"
                    and observed["value"] != request["value"]
                ):
                    failures.append("MANUAL_VALUE_READBACK_MISMATCH")
                if any(
                    observed[key] != pinned[key]
                    for key in (
                        "minimum",
                        "maximum",
                        "step",
                        "default",
                        "capability_flags",
                        "unit",
                    )
                ):
                    failures.append("CONTROL_CAPABILITY_DRIFT")
            if row["reasons"] != failures or row["matched"] is not (not failures):
                return None
        if any(not row["matched"] for row in value["controls"]):
            expected.append("CONTROL_READBACK_MISMATCH")
        return (
            value
            if value["reasons"] == expected
            and value["status"]
            == (
                "READBACK_MISMATCH_UNQUALIFIED"
                if expected
                else "REQUESTED_SETTINGS_OBSERVED_UNQUALIFIED"
            )
            else None
        )

    @classmethod
    def physical(cls, value: Any) -> dict[str, Any] | None:
        extra = (
            {"runtime_inspection"}
            if type(value) is dict and "runtime_inspection" in value
            else set()
        )
        if not (
            cls.exact(
                value,
                {
                    "schema",
                    "status",
                    "source_sha256",
                    "session_id",
                    "reviewed_endpoint",
                    "runtimes",
                    "configuration",
                    "plan",
                    "last_frame",
                    "fault",
                    "publication",
                    "blockers",
                    "physical_authority",
                    "hardware_qualified",
                    "connected",
                    "meaning",
                }
                | extra,
            )
            and value["schema"] == "rocell.wizard_physical_camera.v1"
            and value["status"]
            in (
                "NOT_STARTED",
                "HELD",
                "OBSERVATION_RETAINED",
                "CONFIGURATION_STAGED",
                "CONTENT_VERIFIED",
            )
            and cls.digest(value["source_sha256"])
            and cls.identifier(value["session_id"])
            and cls.string(value["meaning"], 512)
            and cls.codes(value["blockers"])
            and all(
                value[key] is False
                for key in ("physical_authority", "hardware_qualified", "connected")
            )
            and cls.exact(value["runtimes"], {"probe", "capture"})
            and cls.exact(
                value["configuration"], {"capabilities", "candidate", "readback"}
            )
            and cls.exact(value["publication"], {"status", "operation_id"})
            and value["publication"]["status"]
            in ("NOT_PUBLISHED", "PENDING", "CURRENT", "HISTORICAL_HELD")
            and (
                value["publication"]["operation_id"] is None
                or cls.identifier(value["publication"]["operation_id"])
            )
        ):
            return None
        endpoint = value["reviewed_endpoint"]
        if endpoint is not None and not (
            cls.exact(
                endpoint,
                {
                    "endpoint_sha256",
                    "identity_sha256",
                    "metadata_review_binding_sha256",
                    "generic_candidate_sha256",
                },
            )
            and all(cls.digest(item) for item in endpoint.values())
        ):
            return None
        for purpose, runtime in value["runtimes"].items():
            if runtime is not None and not (
                cls.exact(
                    runtime,
                    {
                        "purpose",
                        "registration_sha256",
                        "helper_sha256",
                        "build_record_sha256",
                        "status",
                        "dispatch_enabled",
                        "driver_qualified",
                    },
                )
                and runtime["purpose"] == "FINITE_NATIVE_CAMERA_" + purpose.upper()
                and runtime["status"] == "DORMANT_REVIEW_REQUIRED"
                and runtime["dispatch_enabled"] is False
                and runtime["driver_qualified"] is False
                and all(
                    cls.digest(runtime[key])
                    for key in (
                        "registration_sha256",
                        "helper_sha256",
                        "build_record_sha256",
                    )
                )
            ):
                return None
        plan = value["plan"]
        if plan is not None and not (
            cls.exact(plan, {"plan_sha256", "operation", "stage", "status"})
            and cls.digest(plan["plan_sha256"])
            and plan["operation"] in ("probe", "capture")
            and type(plan["stage"]) is str
            and re.fullmatch(r"[a-z][a-z_]{0,63}", plan["stage"])
            and plan["status"] == "PREPARED_NOT_ADMITTED"
        ):
            return None
        raw = value["configuration"]
        caps = (
            None
            if raw["capabilities"] is None
            else cls.physical_capabilities(raw["capabilities"])
        )
        config = (
            None
            if raw["candidate"] is None
            else cls.physical_candidate(raw["candidate"], caps)
        )
        observed = (
            None
            if raw["readback"] is None
            else cls.physical_readback(raw["readback"], config, caps)
        )
        if (
            (raw["capabilities"] is not None and caps is None)
            or (raw["candidate"] is not None and config is None)
            or (raw["readback"] is not None and observed is None)
            or (
                caps is not None
                and (
                    endpoint is None
                    or caps["binding"]["source_sha256"] != value["source_sha256"]
                    or caps["binding"]["session_id"] != value["session_id"]
                    or caps["binding"]["endpoint_sha256"] != endpoint["endpoint_sha256"]
                )
            )
        ):
            return None
        frame = value["last_frame"]
        if frame is not None and not (
            cls.exact(
                frame,
                {
                    "image_id",
                    "attempt_id",
                    "frame_index",
                    "preview_sha256",
                    "native_frame_sha256",
                    "manifest_sha256",
                    "settings_epoch",
                    "endpoint_sha256",
                    "capture_evidence_sha256",
                    "provenance",
                    "frame_content_verified",
                    "live",
                },
            )
            and (frame["image_id"] is None or cls.identifier(frame["image_id"]))
            and cls.identifier(frame["attempt_id"])
            and cls.integer(frame["frame_index"], 0, 31)
            and all(
                cls.digest(frame[key])
                for key in (
                    "preview_sha256",
                    "native_frame_sha256",
                    "manifest_sha256",
                    "settings_epoch",
                    "endpoint_sha256",
                    "capture_evidence_sha256",
                )
            )
            and frame["provenance"] == "DERIVED_PREVIEW_OF_RETAINED_PHYSICAL_YUY2"
            and frame["frame_content_verified"] is True
            and frame["live"] is False
            and endpoint
            and frame["endpoint_sha256"] == endpoint["endpoint_sha256"]
            and config
            and frame["settings_epoch"] == config["settings_epoch"]
            and observed
            and frame["capture_evidence_sha256"] == observed["capture_evidence_sha256"]
            and frame["attempt_id"] == observed["capture_binding"]["attempt_id"]
            and (
                frame["image_id"] is None
                or (
                    value["publication"]["status"] == "CURRENT"
                    and value["status"] != "HELD"
                    and value["publication"]["operation_id"] is not None
                )
            )
        ):
            return None
        if value["fault"] is not None and _camera_fault(value["fault"]) is None:
            return None
        if value["status"] == "CONTENT_VERIFIED" and (
            not frame
            or not observed
            or observed["status"] != "REQUESTED_SETTINGS_OBSERVED_UNQUALIFIED"
            or observed["process_status"] != "SUCCEEDED_NATIVE_DIAGNOSTIC"
            or observed["native_status"] != "OK"
            or observed["native_receipt_valid"] is not True
            or observed["process_cleanup_confirmed"] is not True
            or observed["native_cleanup_confirmed"] is not True
            or observed["mode_matched"] is not True
            or observed["reasons"]
            or any(not row["matched"] for row in observed["controls"])
        ):
            return None
        if (
            value["status"] == "NOT_STARTED"
            and (
                plan
                or caps
                or config
                or observed
                or frame
                or value["publication"]["status"] != "NOT_PUBLISHED"
            )
        ) or (value["status"] == "CONFIGURATION_STAGED" and config is None):
            return None
        return value


class _PhysicalSetupDisplay(_PhysicalCameraDisplay):
    """Cached storage/requirements display only, not an M1 verifier or adapter."""

    STAGES = (
        "workspace_sources",
        "static_camera_contract",
        "camera_receipt",
        "camera_identity",
        "camera_mode_controls",
        "camera_frame_freshness",
        "optics_intrinsics",
        "static_registration",
        "arm_identity",
        "power_safety",
        "power_on_observation",
        "feedback_only_connection",
        "reference_frame_calibration",
        "noncontact_acceptance",
        "physical_handoff",
    )
    STATES = (
        "PENDING",
        "WAITING_OPERATOR",
        "REVIEW_PENDING",
        "PASS",
        "BLOCKED",
        "INVALIDATED",
        "INCIDENT_HOLD",
        "SIDE_EFFECT_UNCERTAIN",
        "COMPLETE_DIAGNOSTIC",
    )

    @classmethod
    def identifiers(cls, value: Any, maximum: int = 256) -> bool:
        return (
            type(value) is list
            and len(value) <= maximum
            and all(cls.identifier(item) for item in value)
            and len(set(value)) == len(value)
        )

    @classmethod
    def evidence_occurrences(cls, value: Any) -> bool:
        # V2 appends references from each committed event, including repeated
        # citations of an exact receipt during review. This is not an inventory.
        return (
            type(value) is list
            and len(value) <= 256
            and all(cls.identifier(item) for item in value)
        )

    @classmethod
    def verification(cls, value: Any, binding: dict[str, Any]) -> dict[str, Any] | None:
        if not (
            cls.exact(
                value,
                {
                    "schema",
                    "status",
                    "runtime_activation",
                    "cell",
                    "qualification",
                    "attempt_ledger",
                    "quarantine",
                    "session",
                    "leases",
                    "challenge_sha256",
                    "effects_allowed_by_m1_storage",
                    "effect_methods_exposed",
                    "operation_effect",
                    "authority",
                },
            )
            and value["schema"] == "rocell.physical_onboarding_m1_runtime.v1"
            and value["runtime_activation"] is False
            and value["effect_methods_exposed"] is False
            and cls.digest(value["challenge_sha256"])
            and type(value["effects_allowed_by_m1_storage"]) is bool
        ):
            return None
        cell, qualification, attempts, quarantine, session, leases = (
            value[key]
            for key in (
                "cell",
                "qualification",
                "attempt_ledger",
                "quarantine",
                "session",
                "leases",
            )
        )
        cell_flags = {
            "runtime_activation",
            "device_io_authorized",
            "robot_power_authorized",
            "motion_authorized",
            "contact_authorized",
            "automatic_effect_replay_allowed",
        }
        if not (
            cls.exact(
                cell,
                {
                    "schema",
                    "cell_id",
                    "cell_key_sha256",
                    "source_binding_sha256",
                    "stage_plan_sha256",
                    "durability_qualification_sha256",
                    "attempt_ledger_id",
                    "quarantine_ledger_id",
                    "created_at_ns",
                    "physical_release_effect",
                    "cell_sha256",
                }
                | cell_flags,
            )
            and cell["schema"] == "rocell.physical_onboarding_m1_cell.v1"
            and cell["cell_id"] == binding["cell_id"]
            and all(cell[key] is False for key in cell_flags)
            and cell["physical_release_effect"] == "NONE"
            and all(
                cls.digest(cell[key])
                for key in (
                    "cell_key_sha256",
                    "source_binding_sha256",
                    "stage_plan_sha256",
                    "durability_qualification_sha256",
                    "cell_sha256",
                )
            )
            and cls.identifier(cell["attempt_ledger_id"])
            and cls.identifier(cell["quarantine_ledger_id"])
            and cls.integer(cell["created_at_ns"], 0, 2**63 - 1)
            and cls.exact(
                qualification,
                {"anchor_sha256", "startup_report_sha256", "qualified_windows_ntfs"},
            )
            and cls.digest(qualification["anchor_sha256"])
            and cls.digest(qualification["startup_report_sha256"])
            and qualification["qualified_windows_ntfs"] is True
            and cls.exact(
                attempts,
                {
                    "head_sha256",
                    "event_count",
                    "unresolved_attempt_ids",
                    "uncertain_attempt_ids",
                },
            )
            and cls.digest(attempts["head_sha256"])
            and cls.integer(attempts["event_count"], 0, 2**53 - 1)
            and cls.identifiers(attempts["unresolved_attempt_ids"])
            and cls.identifiers(attempts["uncertain_attempt_ids"])
            and cls.exact(
                quarantine,
                {"head_sha256", "event_count", "latched", "clearing_supported"},
            )
            and cls.digest(quarantine["head_sha256"])
            and cls.integer(quarantine["event_count"], 0, 2**53 - 1)
            and type(quarantine["latched"]) is bool
            and quarantine["clearing_supported"] is False
            and cls.exact(
                session,
                {
                    "session_id",
                    "header_sha256",
                    "head_sha256",
                    "evidence_inventory_sha256",
                    "reconciliation_required",
                },
            )
            and session["session_id"] == binding["session_id"]
            and all(
                cls.digest(session[key])
                for key in ("header_sha256", "head_sha256", "evidence_inventory_sha256")
            )
            and type(session["reconciliation_required"]) is bool
            and cls.exact(leases, {"active_or_stale_owners", "reconciliation_required"})
            and cls.identifiers(leases["active_or_stale_owners"])
            and leases["reconciliation_required"]
            is bool(leases["active_or_stale_owners"])
        ):
            return None
        effect_keys = {
            "os_device_metadata_reads",
            "device_opens",
            "camera_frames_captured",
            "serial_transactions",
            "robot_power_operations",
            "robot_commands_sent",
        }
        authority_flags = {
            "device_io_authorized",
            "robot_power_authorized",
            "motion_authorized",
            "descent_authorized",
            "contact_authorized",
        }
        if not (
            cls.exact(value["operation_effect"], effect_keys)
            and all(
                type(value["operation_effect"][key]) is int
                and value["operation_effect"][key] == 0
                for key in effect_keys
            )
            and cls.exact(
                value["authority"],
                authority_flags | {"diagnostic_only", "physical_release_effect"},
            )
            and value["authority"]["diagnostic_only"] is True
            and all(value["authority"][key] is False for key in authority_flags)
            and value["authority"]["physical_release_effect"] == "NONE"
        ):
            return None
        ready = not (
            quarantine["latched"]
            or attempts["unresolved_attempt_ids"]
            or attempts["uncertain_attempt_ids"]
            or session["reconciliation_required"]
            or leases["active_or_stale_owners"]
        )
        status = (
            "M1_STORAGE_READY_ZERO_HARDWARE_AUTHORITY"
            if ready
            else (
                "M1_INTEGRITY_VALID_CELL_QUARANTINED"
                if quarantine["latched"]
                else "M1_INTEGRITY_VALID_RECONCILIATION_REQUIRED"
            )
        )
        return (
            value
            if value["effects_allowed_by_m1_storage"] is ready
            and value["status"] == status
            else None
        )

    @classmethod
    def storage_session(cls, value: Any) -> dict[str, Any] | None:
        if not (
            cls.exact(
                value,
                {
                    "schema",
                    "binding",
                    "status",
                    "operation",
                    "verification",
                    "stages",
                    "error",
                    "partial_store_possible",
                    "initialize_attempted",
                    "physical_authority",
                    "device_io_performed",
                    "hardware_qualified",
                    "replay_allowed",
                },
            )
            and value["schema"] == "rocell.physical_camera_session_view.v1"
            and value["status"]
            in (
                "NOT_INITIALIZED",
                "RUNNING",
                "STORAGE_READY_PENDING",
                "REFRESHED_STORAGE_ONLY",
                "HELD",
            )
            and value["operation"] in (None, "INITIALIZE", "REFRESH")
            and all(
                type(value[key]) is bool
                for key in ("partial_store_possible", "initialize_attempted")
            )
            and all(
                value[key] is False
                for key in (
                    "physical_authority",
                    "device_io_performed",
                    "hardware_qualified",
                    "replay_allowed",
                )
            )
        ):
            return None
        binding = value["binding"]
        if not (
            cls.exact(
                binding,
                {
                    "workspace",
                    "directory",
                    "launch_id",
                    "source_sha256",
                    "cell_id",
                    "session_id",
                },
            )
            and cls.string(binding["workspace"], 4096)
            and cls.string(binding["directory"], 4096)
            and cls.digest(binding["source_sha256"])
            and all(
                type(binding[key]) is str and re.fullmatch(pattern, binding[key])
                for key, pattern in (
                    ("launch_id", r"wizard-[0-9a-f]{32}"),
                    ("cell_id", r"wizard-physical-camera-[0-9a-f]{16}"),
                    ("session_id", r"physical-camera-[0-9a-f]{32}"),
                )
            )
        ):
            return None
        error = value["error"]
        if error is not None and not (
            cls.exact(error, {"code", "type"})
            and cls.codes([error["code"]], 1)
            and error["type"]
            in (
                "PhysicalCameraSessionError",
                "OSError",
                "ValueError",
                "RuntimeError",
                "KeyboardInterrupt",
                "SystemExit",
                "Exception",
            )
        ):
            return None
        checked = (
            None
            if value["verification"] is None
            else cls.verification(value["verification"], binding)
        )
        if (value["verification"] is not None and checked is None) or (
            value["stages"] is None
        ) != (checked is None):
            return None
        if value["stages"] is not None and not (
            type(value["stages"]) is list
            and len(value["stages"]) == 15
            and all(
                cls.exact(
                    row, {"stage", "state", "last_event_sequence", "evidence_ids"}
                )
                and row["stage"] == cls.STAGES[index]
                and row["state"] in cls.STATES
                and (
                    row["last_event_sequence"] is None
                    or cls.integer(row["last_event_sequence"], 0, 2**53 - 1)
                )
                and cls.evidence_occurrences(row["evidence_ids"])
                for index, row in enumerate(value["stages"])
            )
        ):
            return None
        if (
            (
                value["status"] == "NOT_INITIALIZED"
                and (
                    value["operation"] is not None
                    or checked
                    or error
                    or value["initialize_attempted"]
                    or value["partial_store_possible"]
                )
            )
            or (
                value["status"] == "RUNNING"
                and (value["operation"] is None or checked or error)
            )
            or (value["status"] == "HELD" and checked)
        ):
            return None
        if value["status"] in ("STORAGE_READY_PENDING", "REFRESHED_STORAGE_ONLY") and (
            not checked
            or error
            or value["operation"]
            != (
                "INITIALIZE"
                if value["status"] == "STORAGE_READY_PENDING"
                else "REFRESH"
            )
        ):
            return None
        if value["status"] == "STORAGE_READY_PENDING" and (
            not value["initialize_attempted"]
            or not checked
            or not checked["effects_allowed_by_m1_storage"]
            or checked["attempt_ledger"]["event_count"]
            or checked["quarantine"]["event_count"]
            or value["stages"] is None
            or any(
                row["state"] != "PENDING"
                or row["last_event_sequence"] is not None
                or row["evidence_ids"]
                for row in value["stages"]
            )
        ):
            return None
        return value

    @classmethod
    def prerequisites(
        cls, value: Any, binding: dict[str, Any]
    ) -> dict[str, Any] | None:
        files = (
            ("stage_catalog", "software/config/physical_onboarding_stage_catalog.json"),
            ("hazard_register", "software/config/physical_onboarding_hazards.json"),
            ("epoch_policy", "software/config/configuration_epochs.json"),
            (
                "intake_template",
                "hardware/static_overhead_camera/hardware_intake_template.csv",
            ),
        )
        epoch_names = (
            "software_build",
            "camera_support_optics",
            "board_tags_bench",
            "arm_controller_tool",
            "power_system",
            "keyboard_station",
            "phone_station",
            "empty_cell_safety",
        )
        epoch_starts = (
            "workspace_sources",
            "camera_receipt",
            "camera_receipt",
            "arm_identity",
            "power_safety",
            "reference_frame_calibration",
            "reference_frame_calibration",
            "power_safety",
        )
        intake_ids: tuple[list[str], ...] = (
            [],
            [],
            [
                f"INT-{number:03d}"
                for number in (1, 2, 3, 4, 5, 6, 7, 8, 9, 17, 19, 20, 21, 22, 23, 24)
            ],
            ["INT-018"],
        )
        hazard_ids = (
            ["HZ-012"],
            ["HZ-007", "HZ-010"],
            ["HZ-007", "HZ-008", "HZ-009"],
            ["HZ-009"],
        )
        observation_fields = [
            "observed_value",
            "instrument_or_method",
            "observed_at_ns",
            "operator_id",
            "evidence_references",
            "uncertainty_or_limitations",
        ]

        def texts(items: Any, maximum: int = 16, limit: int = 2048) -> bool:
            return (
                type(items) is list
                and 0 < len(items) <= maximum
                and all(cls.string(item, limit) for item in items)
            )

        if not (
            cls.exact(
                value,
                {
                    "schema",
                    "status",
                    "binding",
                    "evidence_sha256",
                    "source_files",
                    "stages",
                    "hazards",
                    "epochs",
                    "metadata_selection",
                    "source_preflight",
                    "missing_requirements",
                    "power_state",
                    "canonical_stage_pass",
                    "physical_authority",
                    "qualified",
                    "device_io_performed",
                    "meaning",
                },
            )
            and value["schema"] == "rocell.physical_camera_prerequisites_summary.v1"
            and value["status"] == "REQUIREMENTS_RETAINED_NOT_ASSESSED"
            and cls.digest(value["evidence_sha256"])
            and cls.exact(
                value["binding"], {"source_sha256", "session_id", "launch_session_id"}
            )
            and value["binding"]
            == {
                "source_sha256": binding["source_sha256"],
                "session_id": binding["session_id"],
                "launch_session_id": binding["launch_id"],
            }
            and value["power_state"] == "UNKNOWN"
            and all(
                value[key] is False
                for key in (
                    "canonical_stage_pass",
                    "physical_authority",
                    "qualified",
                    "device_io_performed",
                )
            )
            and cls.string(value["meaning"], 512)
            and type(value["source_files"]) is list
            and len(value["source_files"]) == 4
            and all(
                cls.exact(row, {"role", "relative_path", "sha256", "bytes"})
                and row["role"] == files[index][0]
                and row["relative_path"] == files[index][1]
                and cls.digest(row["sha256"])
                and cls.integer(row["bytes"], 1, 65536)
                for index, row in enumerate(value["source_files"])
            )
            and type(value["stages"]) is list
            and len(value["stages"]) == 4
            and type(value["hazards"]) is list
            and len(value["hazards"]) == 5
            and type(value["epochs"]) is list
            and len(value["epochs"]) == 8
        ):
            return None
        for index, stage in enumerate(value["stages"]):
            if not (
                cls.exact(
                    stage,
                    {
                        "stage",
                        "status",
                        "required_effect_classes",
                        "actuator_power_requirement",
                        "owned_artifacts",
                        "hazard_ids",
                        "intake_rows",
                        "required_records",
                    },
                )
                and stage["stage"] == cls.STAGES[index]
                and stage["status"] == "REQUIREMENTS_ONLY"
                and stage["required_effect_classes"]
                == (["READ_ONLY_OS_INVENTORY"] if index == 3 else ["NO_DEVICE_IO"])
                and stage["actuator_power_requirement"] == "DISCONNECTED_REQUIRED"
                and texts(stage["owned_artifacts"], 8, 96)
                and stage["hazard_ids"] == hazard_ids[index]
                and cls.codes(stage["required_records"], 8)
                and type(stage["intake_rows"]) is list
                and len(stage["intake_rows"]) == len(intake_ids[index])
            ):
                return None
            for offset, row in enumerate(stage["intake_rows"]):
                if not (
                    cls.exact(
                        row,
                        {
                            "record_id",
                            "assembly",
                            "measurement",
                            "unit",
                            "candidate_or_requirement",
                            "template_phase",
                            "template_status",
                            "template_notes",
                            "required_observation_fields",
                            "observation",
                            "acceptance",
                        },
                    )
                    and row["record_id"] == intake_ids[index][offset]
                    and all(
                        row[key] == "" or cls.string(row[key], 4096)
                        for key in (
                            "assembly",
                            "measurement",
                            "unit",
                            "candidate_or_requirement",
                            "template_phase",
                            "template_notes",
                        )
                    )
                    and row["template_status"]
                    in (
                        "NOT_CAPTURED",
                        "NOT_CREATED",
                        "NOT_MEASURED",
                        "NOT_RECORDED",
                        "NOT_TESTED",
                        "OPEN_LIMIT",
                    )
                    and row["required_observation_fields"] == observation_fields
                    and row["observation"] is None
                    and cls.exact(
                        row["acceptance"],
                        {
                            "status",
                            "owner_stage",
                            "prerequisites",
                            "measurement_required",
                        },
                    )
                    and row["acceptance"]["measurement_required"] is True
                ):
                    return None
                deferred = row["record_id"] == "INT-005"
                if (
                    row["acceptance"]["status"]
                    != ("DEFERRED_LIMIT" if deferred else "NOT_ASSESSED")
                    or row["acceptance"]["owner_stage"]
                    != ("noncontact_acceptance" if deferred else stage["stage"])
                    or row["acceptance"]["prerequisites"]
                    != (["TARGET_ACCURACY_BUDGET_CLOSED"] if deferred else [])
                ):
                    return None
        for index, hazard in enumerate(value["hazards"]):
            if not (
                cls.exact(
                    hazard,
                    {
                        "id",
                        "title",
                        "severity",
                        "status",
                        "evidence_stages",
                        "invalidation_epochs",
                        "controls",
                        "required_evidence",
                        "fail_safe",
                        "residual_status",
                    },
                )
                and hazard["id"]
                == ("HZ-007", "HZ-008", "HZ-009", "HZ-010", "HZ-012")[index]
                and cls.string(hazard["title"], 512)
                and hazard["severity"] == "HIGH"
                and hazard["status"] == "OPEN_BLOCKING"
                and type(hazard["evidence_stages"]) is list
                and 0 < len(hazard["evidence_stages"]) <= 15
                and all(stage in cls.STAGES for stage in hazard["evidence_stages"])
                and type(hazard["invalidation_epochs"]) is list
                and 0 < len(hazard["invalidation_epochs"]) <= 8
                and all(epoch in epoch_names for epoch in hazard["invalidation_epochs"])
                and texts(hazard["controls"])
                and texts(hazard["required_evidence"])
                and cls.codes([hazard["fail_safe"]], 1)
                and hazard["residual_status"]
                == "UNASSESSED_REQUIRES_RECEIVED_HARDWARE_EVIDENCE"
            ):
                return None
        for index, epoch in enumerate(value["epochs"]):
            if not (
                cls.exact(
                    epoch,
                    {
                        "epoch_id",
                        "status",
                        "value",
                        "description",
                        "change_triggers",
                        "invalidates_from_stage",
                        "required_bindings",
                    },
                )
                and epoch["epoch_id"] == epoch_names[index]
                and epoch["status"] == "UNMEASURED"
                and epoch["value"] is None
                and cls.string(epoch["description"], 512)
                and epoch["invalidates_from_stage"] == epoch_starts[index]
                and texts(epoch["change_triggers"], 16, 96)
                and texts(epoch["required_bindings"], 16, 96)
            ):
                return None
        selected, preflight = value["metadata_selection"], value["source_preflight"]
        if selected is not None and not (
            cls.exact(
                selected,
                {
                    "endpoint_sha256",
                    "identity_sha256",
                    "metadata_review_binding_sha256",
                    "generic_candidate_sha256",
                },
            )
            and all(cls.digest(item) for item in selected.values())
        ):
            return None
        if preflight is not None and not (
            cls.exact(
                preflight,
                {
                    "report_sha256",
                    "outcome",
                    "origin_session_id",
                    "canonical_stage_pass",
                    "power_state",
                },
            )
            and cls.digest(preflight["report_sha256"])
            and cls.identifier(preflight["origin_session_id"])
            and preflight["outcome"] in ("FILE_CHECKS_COHERENT", "HELD")
            and preflight["canonical_stage_pass"] is False
            and preflight["power_state"] == "UNKNOWN"
        ):
            return None
        missing = [
            "REQUIREMENTS_ARE_NOT_OBSERVATIONS_OR_ACCEPTANCE",
            "DISCONNECTED_REQUIRED_NOT_OBSERVED",
            "HZ_012_QUALIFICATION_EVIDENCE_NOT_ASSESSED",
            "STATIC_CAMERA_CONTRACT_NOT_ASSESSED_BY_THIS_COLLECTION",
            "RECEIVED_CAMERA_AND_PASSIVE_WORKCELL_NOT_MEASURED",
            "RECEIVED_LABEL_TO_USB_CORRELATION_NOT_ASSESSED",
            "PERSISTENT_IDENTITY_STABILITY_NOT_QUALIFIED",
            "ALL_EIGHT_EPOCH_DEPENDENCIES_UNMEASURED",
            "NATIVE_ACTIVATION_AND_PHYSICAL_STAGE_GATES_REMAIN_HELD",
        ]
        missing.append(
            "SOURCE_PREFLIGHT_ONLY_NOT_CANONICAL_ACCEPTANCE"
            if preflight
            else "SOURCE_PREFLIGHT_NOT_SUPPLIED"
        )
        if preflight and preflight["outcome"] != "FILE_CHECKS_COHERENT":
            missing.append("SOURCE_PREFLIGHT_HELD")
        missing.append(
            "METADATA_SELECTION_ONLY_NOT_RECEIVED_UNIT_QUALIFICATION"
            if selected
            else "CURRENT_CAMERA_SELECTION_NOT_SUPPLIED"
        )
        return value if value["missing_requirements"] == missing else None

    @classmethod
    def reopening(cls, value: Any, launch: str, source: str) -> dict[str, Any] | None:
        reason_codes = {
            "NO_STORE_ROOT",
            "UNRECOGNIZED_ENTRY",
            "UNSAFE_PATH",
            "METADATA_LIMIT",
            "AMBIGUOUS_STORE",
            "INVALID_METADATA",
            "DOMAIN_MISMATCH",
            "LINEAGE_MISMATCH",
            "METADATA_CHANGED",
            "SOURCE_CHANGED",
            "CANCELLED",
            "DEADLINE_EXPIRED",
            "DISCOVERY_LIMIT",
            "REGISTRY_INVALIDATED",
            "INVALID_REQUEST",
            "REGISTRY_BUSY",
            "STALE_CHOICE",
        }

        def launch_id(item: Any) -> bool:
            return (
                type(item) is str
                and re.fullmatch(r"wizard-[0-9a-f]{32}", item) is not None
            )

        if not (
            cls.exact(
                value,
                {
                    "schema",
                    "status",
                    "current_launch_id",
                    "source_sha256",
                    "discovery_sha256",
                    "stores",
                    "issues",
                    "invalidation_reason",
                    "physical_authority",
                    "device_io_performed",
                    "meaning",
                },
            )
            and value["schema"] == "rocell.physical_camera_reopen_registry.v1"
            and value["status"]
            in ("NOT_DISCOVERED", "DISCOVERED", "HELD", "INVALIDATED")
            and value["current_launch_id"] == launch
            and value["source_sha256"] == source
            and value["physical_authority"] is False
            and value["device_io_performed"] is False
            and cls.string(value["meaning"], 512)
            and type(value["stores"]) is list
            and len(value["stores"]) <= 32
            and type(value["issues"]) is list
            and len(value["issues"]) <= 33
            and (
                value["discovery_sha256"] is None
                or cls.digest(value["discovery_sha256"])
            )
        ):
            return None
        for row in value["stores"]:
            if not (
                cls.exact(
                    row,
                    {
                        "choice_id",
                        "origin_launch_id",
                        "cell_id",
                        "session_id",
                        "source_binding_sha256",
                        "header_sha256",
                        "descriptor_sha256",
                        "source_matches",
                        "selectable",
                        "status",
                        "physical_authority",
                    },
                )
                and launch_id(row["origin_launch_id"])
                and type(row["cell_id"]) is str
                and re.fullmatch(r"wizard-physical-camera-[0-9a-f]{16}", row["cell_id"])
                and type(row["session_id"]) is str
                and re.fullmatch(r"physical-camera-[0-9a-f]{32}", row["session_id"])
                and all(
                    cls.digest(row[key])
                    for key in (
                        "source_binding_sha256",
                        "header_sha256",
                        "descriptor_sha256",
                    )
                )
                and row["physical_authority"] is False
                and type(row["source_matches"]) is bool
                and row["selectable"] is row["source_matches"]
                and row["status"]
                == (
                    "METADATA_DISCOVERED_NOT_OPENED"
                    if row["selectable"]
                    else "SOURCE_DRIFT_HELD"
                )
                and (
                    type(row["choice_id"]) is str
                    and re.fullmatch(r"reopen-[0-9a-f]{32}", row["choice_id"])
                    if row["selectable"]
                    else row["choice_id"] is None
                )
            ):
                return None
        tokens = [row["choice_id"] for row in value["stores"] if row["selectable"]]
        if len(set(tokens)) != len(tokens) or len(
            {row["origin_launch_id"] for row in value["stores"]}
        ) != len(value["stores"]):
            return None
        for issue in value["issues"]:
            if not (
                cls.exact(issue, {"store_label", "code", "meaning"})
                and (issue["store_label"] is None or launch_id(issue["store_label"]))
                and type(issue["code"]) is str
                and issue["code"] in reason_codes
                and cls.string(issue["meaning"], 512)
            ):
                return None
        if value["status"] == "DISCOVERED":
            if (
                not cls.digest(value["discovery_sha256"])
                or value["invalidation_reason"] is not None
            ):
                return None
        elif (
            value["discovery_sha256"] is not None
            or value["stores"]
            or (value["status"] != "HELD" and value["issues"])
        ):
            return None
        if value["status"] == "INVALIDATED":
            if (
                type(value["invalidation_reason"]) is not str
                or value["invalidation_reason"] not in reason_codes
            ):
                return None
        elif value["invalidation_reason"] is not None:
            return None
        return value

    @classmethod
    def setup(cls, value: Any) -> dict[str, Any] | None:
        version_two = type(value) is dict and value.get("schema") in (
            "rocell.wizard_physical_camera_setup.v2",
            "rocell.wizard_physical_camera_setup.v3",
        )
        extra_keys = (
            {"origin_launch_id", "requirements_provenance", "reopening"}
            if version_two
            else set()
        )
        if type(value) is dict and "source_workflow" in value:
            extra_keys.add("source_workflow")
        if (
            type(value) is dict
            and value.get("schema") == "rocell.wizard_physical_camera_setup.v3"
        ):
            extra_keys.add("configuration_records")
        if not (
            cls.exact(
                value,
                {
                    "schema",
                    "source_sha256",
                    "launch_session_id",
                    "session",
                    "prerequisites",
                    "publication",
                    "physical_authority",
                    "hardware_qualified",
                    "meaning",
                }
                | extra_keys,
            )
            and value["schema"]
            in (
                "rocell.wizard_physical_camera_setup.v1",
                "rocell.wizard_physical_camera_setup.v2",
                "rocell.wizard_physical_camera_setup.v3",
            )
            and cls.digest(value["source_sha256"])
            and type(value["launch_session_id"]) is str
            and re.fullmatch(r"wizard-[0-9a-f]{32}", value["launch_session_id"])
            and value["physical_authority"] is False
            and value["hardware_qualified"] is False
            and cls.string(value["meaning"], 512)
            and cls.exact(value["publication"], {"status", "operation_id"})
            and value["publication"]["status"]
            in ("NOT_PUBLISHED", "PENDING", "CURRENT", "HISTORICAL_HELD")
            and (
                value["publication"]["operation_id"] is None
                or cls.identifier(value["publication"]["operation_id"])
            )
        ):
            return None
        current = cls.storage_session(value["session"])
        if (
            current is None
            or current["binding"]["source_sha256"] != value["source_sha256"]
            or current["binding"]["launch_id"]
            != (
                value["origin_launch_id"] if version_two else value["launch_session_id"]
            )
        ):
            return None
        if (
            value["prerequisites"] is not None
            and cls.prerequisites(value["prerequisites"], current["binding"]) is None
        ):
            return None
        if version_two:
            expected = (
                "NONE"
                if value["prerequisites"] is None
                else (
                    "CURRENT_LAUNCH_ORIGINAL"
                    if value["origin_launch_id"] == value["launch_session_id"]
                    else "REOPENED_ORIGINAL_CONTEXT"
                )
            )
            if (
                value["requirements_provenance"] != expected
                or cls.reopening(
                    value["reopening"],
                    value["launch_session_id"],
                    value["source_sha256"],
                )
                is None
                or (
                    value["publication"]["status"] in ("PENDING", "HISTORICAL_HELD")
                    and value["prerequisites"] is not None
                )
            ):
                return None
        return value


class _PhysicalConfigurationRecordsDisplay(_PhysicalSetupDisplay):
    """Compact original dependencies; never a verifier or admission decision."""

    DOMAINS = (
        "software_build",
        "camera_support_optics",
        "board_tags_bench",
        "arm_controller_tool",
        "power_system",
        "keyboard_station",
        "phone_station",
        "empty_cell_safety",
    )
    STARTS = (0, 2, 2, 8, 9, 12, 12, 9)
    BINDINGS = (
        (
            ("build_snapshot", 0),
            ("source_binding", 0),
            ("dependency_receipt", 0),
            ("provider_hashes", 0),
        ),
        (
            ("camera_receipt", 2),
            ("camera_identity", 3),
            ("camera_mode_controls", 4),
            ("support_witnesses", 7),
        ),
        (
            ("board_measurement", 2),
            ("tag_map", 7),
            ("bench_identity", 2),
            ("board_reseat_test", 7),
        ),
        (
            ("arm_identity", 8),
            ("controller_identity", 11),
            ("firmware_identity", 11),
            ("tool_identity", 12),
        ),
        (
            ("power_topology", 9),
            ("cutoff_test", 9),
            ("containment_review", 9),
            ("discharge_test", 9),
        ),
        (("keyboard_identity", 12), ("keyboard_pose", 12), ("keyboard_target_map", 12)),
        (
            ("phone_identity", 12),
            ("phone_pose", 12),
            ("screen_homography", 12),
            ("phone_target_map", 12),
            ("ui_state", 12),
        ),
        (
            ("installed_object_inventory", 9),
            ("collision_geometry", 13),
            ("startup_sweep", 10),
            ("empty_cell_witness", 9),
        ),
    )
    STATUS_KEYS = {
        "RETAINED_REFERENCE_UNASSESSED": "retained",
        "MISSING_PREDECESSOR": "missing_predecessors",
        "MISSING_CURRENT_OUTPUT": "missing_current_outputs",
        "PENDING_CURRENT_OUTPUT": "pending_current_outputs",
        "PENDING_FUTURE_OUTPUT": "pending_future_outputs",
    }

    @classmethod
    def projection(cls, value: Any, setup: dict[str, Any]) -> dict[str, Any] | None:
        if not (
            cls.exact(
                value,
                {
                    "schema",
                    "status",
                    "summary",
                    "physical_authority",
                    "hardware_qualified",
                },
            )
            and value["schema"] == "rocell.wizard_physical_configuration_records.v1"
            and value["status"] in ("NOT_RETAINED", "CURRENT", "HISTORICAL_HELD")
            and value["physical_authority"] is False
            and value["hardware_qualified"] is False
        ):
            return None
        if setup["publication"]["status"] == "PENDING" and (
            value["status"] != "NOT_RETAINED" or value["summary"] is not None
        ):
            return None
        if value["status"] == "NOT_RETAINED":
            return value if value["summary"] is None else None
        s = value["summary"]
        if s is None:
            return value if value["status"] == "HISTORICAL_HELD" else None
        verified, prerequisites = (
            setup["session"]["verification"],
            setup["prerequisites"],
        )
        if value["status"] == "CURRENT" and (
            setup["publication"]["status"] != "CURRENT"
            or not verified
            or not prerequisites
        ):
            return None
        if not (
            cls.exact(
                s,
                {
                    "schema",
                    "record_sha256",
                    "binding",
                    "original_snapshot",
                    "boundary",
                    "entries",
                    "coverage",
                    "physical_authority",
                    "qualified",
                    "canonical_stage_pass",
                    "admission_allowed",
                    "device_io_performed",
                    "meaning",
                },
            )
            and s["schema"] == "rocell.physical_configuration_epochs_summary.v1"
            and cls.digest(s["record_sha256"])
            and cls.string(s["meaning"], 512)
            and all(
                s[key] is False
                for key in (
                    "physical_authority",
                    "qualified",
                    "canonical_stage_pass",
                    "admission_allowed",
                    "device_io_performed",
                )
            )
        ):
            return None
        b, snapshot, boundary = s["binding"], s["original_snapshot"], s["boundary"]
        if not (
            cls.exact(
                b,
                {
                    "source_sha256",
                    "source_binding_sha256",
                    "session_id",
                    "cell_id",
                    "origin_launch_id",
                    "session_header_sha256",
                    "prerequisites_sha256",
                    "epoch_policy_sha256",
                    "stage_catalog_sha256",
                },
            )
            and all(
                cls.digest(b[key])
                for key in (
                    "source_sha256",
                    "source_binding_sha256",
                    "session_header_sha256",
                    "prerequisites_sha256",
                    "epoch_policy_sha256",
                    "stage_catalog_sha256",
                )
            )
            and b["source_sha256"] == setup["source_sha256"]
            and b["session_id"] == setup["session"]["binding"]["session_id"]
            and b["cell_id"] == setup["session"]["binding"]["cell_id"]
            and b["origin_launch_id"] == setup["session"]["binding"]["launch_id"]
            and (
                not verified
                or (
                    b["session_header_sha256"] == verified["session"]["header_sha256"]
                    and b["source_binding_sha256"]
                    == verified["cell"]["source_binding_sha256"]
                )
            )
            and (
                not prerequisites
                or (
                    b["prerequisites_sha256"] == prerequisites["evidence_sha256"]
                    and b["epoch_policy_sha256"]
                    == next(
                        row["sha256"]
                        for row in prerequisites["source_files"]
                        if row["role"] == "epoch_policy"
                    )
                    and b["stage_catalog_sha256"]
                    == next(
                        row["sha256"]
                        for row in prerequisites["source_files"]
                        if row["role"] == "stage_catalog"
                    )
                )
            )
            and cls.exact(
                snapshot,
                {
                    "head_sha256",
                    "event_count",
                    "evidence_inventory_sha256",
                    "reference_count",
                },
            )
            and cls.digest(snapshot["head_sha256"])
            and cls.digest(snapshot["evidence_inventory_sha256"])
            and cls.integer(snapshot["event_count"], 0, 512)
            and cls.integer(snapshot["reference_count"], 0, 32)
            and cls.exact(boundary, {"stage", "phase"})
            and boundary["stage"] in cls.STAGES
            and boundary["phase"] in ("BEFORE_STAGE", "AFTER_STAGE")
            and type(s["entries"]) is list
            and len(s["entries"]) == 8
        ):
            return None
        counts = dict.fromkeys(cls.STATUS_KEYS.values(), 0)
        index = cls.STAGES.index(boundary["stage"])
        for domain, entry in enumerate(s["entries"]):
            if not (
                cls.exact(
                    entry, {"epoch_id", "invalidates_from_stage", "status", "bindings"}
                )
                and entry["epoch_id"] == cls.DOMAINS[domain]
                and entry["invalidates_from_stage"] == cls.STAGES[cls.STARTS[domain]]
                and type(entry["bindings"]) is list
                and len(entry["bindings"]) == len(cls.BINDINGS[domain])
            ):
                return None
            retained = 0
            for row, (identifier, owner) in zip(
                entry["bindings"], cls.BINDINGS[domain]
            ):
                relation = (
                    "PREDECESSOR"
                    if owner < index
                    else "CURRENT_STAGE" if owner == index else "FUTURE_STAGE"
                )
                if not (
                    cls.exact(
                        row,
                        {
                            "binding_id",
                            "owner_stage",
                            "relative_position",
                            "status",
                            "evidence_count",
                            "payload_sha256s",
                        },
                    )
                    and row["binding_id"] == identifier
                    and row["owner_stage"] == cls.STAGES[owner]
                    and row["relative_position"] == relation
                    and cls.integer(row["evidence_count"], 0, 4)
                    and row["evidence_count"] <= snapshot["reference_count"]
                    and type(row["payload_sha256s"]) is list
                    and len(row["payload_sha256s"]) == row["evidence_count"]
                    and all(cls.digest(digest) for digest in row["payload_sha256s"])
                ):
                    return None
                expected = (
                    "RETAINED_REFERENCE_UNASSESSED"
                    if row["evidence_count"]
                    else (
                        "MISSING_PREDECESSOR"
                        if owner < index
                        else (
                            "PENDING_FUTURE_OUTPUT"
                            if owner > index
                            else (
                                "PENDING_CURRENT_OUTPUT"
                                if boundary["phase"] == "BEFORE_STAGE"
                                else "MISSING_CURRENT_OUTPUT"
                            )
                        )
                    )
                )
                if row["status"] != expected:
                    return None
                counts[cls.STATUS_KEYS[expected]] += 1
                retained += bool(row["evidence_count"])
            expected_entry = (
                "UNOBSERVED"
                if not retained
                else (
                    "REFERENCES_RETAINED_UNASSESSED"
                    if retained == len(entry["bindings"])
                    else "PARTIALLY_REFERENCED"
                )
            )
            if entry["status"] != expected_entry:
                return None
        if not (
            cls.exact(s["coverage"], {"total_bindings", *counts})
            and type(s["coverage"]["total_bindings"]) is int
            and s["coverage"]["total_bindings"] == 32
            and all(
                cls.integer(s["coverage"][key], 0, 32) and s["coverage"][key] == count
                for key, count in counts.items()
            )
        ):
            return None
        return value


class _WorkspaceSourceDisplay(_PhysicalSetupDisplay):
    """Structural cached subjects only; full codec/M1 checks remain backend-owned."""

    FLAGS = {"physical_authority", "canonical_stage_pass", "device_io_performed"}
    CHECKS = (
        "controlled_build_sources",
        "foundation_semantics",
        "unchanged_file_snapshot",
        "runtime_fail_closed",
        "launcher_and_bootstrap_present",
        "base_software_ready",
        "static_camera_plan_selected",
    )
    MISSING = (
        "DISCONNECTED_ACTUATOR_POWER_NOT_OBSERVED",
        "HZ_012_QUALIFICATION_EVIDENCE_MISSING",
        "STATIC_CAMERA_RELEASE_NOT_QUALIFIED",
    )

    @classmethod
    def label(cls, value: Any) -> bool:
        return (
            cls.string(value, 128)
            and value.strip() == value
            and not any(unicodedata.category(char).startswith("C") for char in value)
        )

    @staticmethod
    def identifier(value: Any) -> bool:
        return (
            type(value) is str
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value) is not None
        )

    @classmethod
    def bound(cls, value: Any) -> bool:
        return (
            cls.exact(
                value,
                {
                    "source_sha256",
                    "session_id",
                    "origin_launch_id",
                    "collection_launch_id",
                    "header_sha256",
                    "prerequisites_sha256",
                    "operator_id",
                },
            )
            and all(
                cls.digest(value[key])
                for key in ("source_sha256", "header_sha256", "prerequisites_sha256")
            )
            and all(
                cls.identifier(value[key])
                for key in ("session_id", "origin_launch_id", "collection_launch_id")
            )
            and cls.label(value["operator_id"])
        )

    @classmethod
    def no_authority(cls, value: Any) -> bool:
        return (
            all(value[key] is False for key in cls.FLAGS)
            and value["power_state"] == "UNKNOWN"
        )

    @classmethod
    def software(cls, value: Any) -> bool:
        return (
            type(value) is list
            and len(value) == len(cls.CHECKS)
            and all(
                cls.exact(row, {"check_id", "passed"})
                and row["check_id"] == cls.CHECKS[index]
                and type(row["passed"]) is bool
                and (index >= 3 or row["passed"] is True)
                for index, row in enumerate(value)
            )
        )

    @classmethod
    def projection(cls, value: Any, setup: dict[str, Any]) -> dict[str, Any] | None:
        supplemental = (
            type(value) is dict
            and value.get("schema") == "rocell.wizard_workspace_source_workflow.v2"
        )
        if (
            not cls.exact(
                value,
                {
                    "schema",
                    "status",
                    "receipt",
                    "assessment",
                    "review",
                    *cls.FLAGS,
                    "power_state",
                }
                | (
                    {"original_source_state", "supplementary"}
                    if supplemental
                    else set()
                ),
            )
            or value["schema"]
            not in (
                "rocell.wizard_workspace_source_workflow.v1",
                "rocell.wizard_workspace_source_workflow.v2",
            )
            or not cls.no_authority(value)
            or value["status"]
            not in (
                "NOT_STARTED",
                "REVIEW_PENDING",
                "REVIEWED_BLOCKED",
                "HISTORICAL_HELD",
            )
        ):
            return None
        receipt, assessment, review = (
            value["receipt"],
            value["assessment"],
            value["review"],
        )
        if supplemental and value["status"] == "NOT_STARTED":
            return (
                value
                if (
                    value["original_source_state"] == "BLOCKED"
                    and value["supplementary"] is None
                    and receipt is None
                    and assessment is None
                    and review is None
                    and setup["publication"]["status"] == "PENDING"
                )
                else None
            )
        if supplemental and not (
            value["original_source_state"] == "BLOCKED"
            and value["status"] in ("REVIEWED_BLOCKED", "HISTORICAL_HELD")
            and receipt is not None
            and assessment is not None
            and review is not None
            and cls.exact(value["supplementary"], {"collection_id", "state"})
            and type(value["supplementary"]["collection_id"]) is str
            and re.fullmatch(
                r"intake-[0-9a-f]{32}", value["supplementary"]["collection_id"]
            )
            and value["supplementary"]["state"]
            in ("WAITING_OPERATOR", "REVIEW_PENDING", "BLOCKED")
        ):
            return None
        if value["status"] == "NOT_STARTED":
            return (
                value
                if receipt is None and assessment is None and review is None
                else None
            )
        if receipt is not None and (
            not cls.exact(
                receipt,
                {
                    "schema",
                    "status",
                    "binding",
                    "receipt_sha256",
                    "software_checks",
                    "source_file_count",
                    "foundation_contract_count",
                    "host_blocker_count",
                    *cls.FLAGS,
                    "power_state",
                },
            )
            or receipt["schema"] != "rocell.workspace_source_receipt_summary.v1"
            or receipt["status"] != "FILE_FACTS_COLLECTED"
            or not cls.bound(receipt["binding"])
            or not cls.digest(receipt["receipt_sha256"])
            or not cls.software(receipt["software_checks"])
            or not cls.no_authority(receipt)
            or not cls.integer(receipt["source_file_count"], 0, 128)
            or not cls.integer(receipt["foundation_contract_count"], 0, 32)
            or not cls.integer(receipt["host_blocker_count"], 0, 64)
        ):
            return None
        if assessment is not None and (
            receipt is None
            or not cls.exact(
                assessment,
                {
                    "schema",
                    "status",
                    "verdict",
                    "binding",
                    "receipt_sha256",
                    "assessment_sha256",
                    "software_checks",
                    "missing_requirements",
                    *cls.FLAGS,
                    "power_state",
                },
            )
            or assessment["schema"] != "rocell.workspace_source_assessment_summary.v1"
            or assessment["status"] != "ASSESSED"
            or assessment["verdict"] != "BLOCKED"
            or not cls.bound(assessment["binding"])
            or assessment["binding"] != receipt["binding"]
            or assessment["receipt_sha256"] != receipt["receipt_sha256"]
            or not cls.digest(assessment["assessment_sha256"])
            or not cls.software(assessment["software_checks"])
            or not cls.no_authority(assessment)
            or assessment["software_checks"] != receipt["software_checks"]
            or assessment["missing_requirements"]
            != [
                *cls.MISSING,
                *(
                    ["SOFTWARE_PREREQUISITES_NOT_READY"]
                    if any(not row["passed"] for row in assessment["software_checks"])
                    else []
                ),
            ]
        ):
            return None
        if review is not None and (
            assessment is None
            or receipt is None
            or not cls.exact(
                review,
                {
                    "schema",
                    "status",
                    "verdict",
                    "binding",
                    "receipt_sha256",
                    "assessment_sha256",
                    "review_sha256",
                    "reviewer_id",
                    "review_launch_id",
                    "distinct_operator_labels",
                    "authenticated_independent_people",
                    *cls.FLAGS,
                    "power_state",
                },
            )
            or review["schema"] != "rocell.workspace_source_review_summary.v1"
            or review["status"] != "ACKNOWLEDGED_BLOCKED"
            or review["verdict"] != "BLOCKED"
            or not cls.bound(review["binding"])
            or review["binding"] != receipt["binding"]
            or review["receipt_sha256"] != receipt["receipt_sha256"]
            or review["assessment_sha256"] != assessment["assessment_sha256"]
            or not cls.digest(review["review_sha256"])
            or not cls.label(review["reviewer_id"])
            or review["reviewer_id"] == receipt["binding"]["operator_id"]
            or not cls.identifier(review["review_launch_id"])
            or review["distinct_operator_labels"] is not True
            or review["authenticated_independent_people"] is not False
            or not cls.no_authority(review)
        ):
            return None
        if value["status"] == "REVIEW_PENDING" and (
            receipt is None or assessment is None or review is not None
        ):
            return None
        if value["status"] == "REVIEWED_BLOCKED" and (
            receipt is None or assessment is None or review is None
        ):
            return None
        if value["status"] in ("REVIEW_PENDING", "REVIEWED_BLOCKED"):
            assert receipt is not None
            original, verified, prerequisites = (
                setup["session"]["binding"],
                setup["session"]["verification"],
                setup["prerequisites"],
            )
            if (
                setup["publication"]["status"] != "CURRENT"
                or verified is None
                or prerequisites is None
                or receipt["binding"]["source_sha256"] != setup["source_sha256"]
                or receipt["binding"]["session_id"] != original["session_id"]
                or receipt["binding"]["origin_launch_id"] != original["launch_id"]
                or receipt["binding"]["header_sha256"]
                != verified["session"]["header_sha256"]
                or receipt["binding"]["prerequisites_sha256"]
                != prerequisites["evidence_sha256"]
                or setup["session"]["stages"][0]["stage"] != "workspace_sources"
                or setup["session"]["stages"][0]["state"]
                != (
                    value["supplementary"]["state"]
                    if supplemental
                    else (
                        "REVIEW_PENDING"
                        if value["status"] == "REVIEW_PENDING"
                        else "BLOCKED"
                    )
                )
            ):
                return None
        return value


class _SourceReassessmentDisplay(_PhysicalSetupDisplay):
    """Cached stage-only subjects; never a qualification or admission verifier."""

    FLAGS = {
        "physical_authority",
        "hardware_qualified",
        "native_release_allowed",
        "device_io_performed",
    }
    CHECKS: tuple[str, ...] = (
        "controlled_build_sources",
        "foundation_semantics",
        "unchanged_file_snapshot",
        "runtime_fail_closed",
        "launcher_and_bootstrap_present",
        "base_software_ready",
        "static_camera_plan_selected",
    )
    OWNERSHIP = (
        "DURABILITY_LOCKING",
        "ORDERED_CROSS_PROCESS_OWNERSHIP",
        "LIVE_CONTENDER_DENIED",
        "CLEAN_RELEASE_LINEAGE",
        "CRASH_STALE_OWNER_DENIED",
        "INJECTED_PROCESS_START_MISMATCH_DENIED",
        "ORIGINAL_M1_NO_REPLAY",
    )
    ACTIONS: tuple[str, ...] = (
        "physical_source_isolation_files_discover",
        "physical_source_qualify",
        "physical_source_qualification_review",
        "physical_static_contract_begin",
    )

    @staticmethod
    def actor(value: Any) -> bool:
        return (
            type(value) is str
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value) is not None
        )

    @staticmethod
    def launch(value: Any) -> bool:
        return (
            type(value) is str
            and re.fullmatch(r"wizard-[0-9a-f]{32}", value) is not None
        )

    @classmethod
    def projection(cls, value: Any, view: Any) -> dict[str, Any] | None:
        if not (
            cls.exact(
                value,
                {
                    "schema",
                    "status",
                    "source_sha256",
                    "launch_session_id",
                    "original_context",
                    "publication",
                    "stage_states",
                    "qualification",
                    "next_action",
                    "meaning",
                }
                | cls.FLAGS,
            )
            and value["schema"] == "rocell.wizard_source_reassessment.v1"
            and value["status"]
            in (
                "NOT_STARTED",
                "REVIEW_PENDING",
                "REVIEWED_PASS",
                "REVIEWED_BLOCKED",
                "INCOMPLETE_HELD",
                "HISTORICAL_HELD",
            )
            and cls.digest(value["source_sha256"])
            and cls.launch(value["launch_session_id"])
            and all(value[key] is False for key in cls.FLAGS)
            and cls.string(value["meaning"], 512)
            and cls.exact(value["publication"], {"status", "operation_id"})
            and value["publication"]["status"]
            in ("NOT_PUBLISHED", "PENDING", "CURRENT", "HISTORICAL_HELD")
            and (
                value["publication"]["operation_id"] is None
                or cls.identifier(value["publication"]["operation_id"])
            )
            and (value["next_action"] is None or value["next_action"] in cls.ACTIONS)
        ):
            return None
        context, stages, q = (
            value["original_context"],
            value["stage_states"],
            value["qualification"],
        )
        if context is not None and not (
            cls.exact(
                context,
                {
                    "source_sha256",
                    "session_id",
                    "cell_id",
                    "origin_launch_id",
                    "header_sha256",
                    "prerequisites_sha256",
                },
            )
            and all(
                cls.digest(context[key])
                for key in ("source_sha256", "header_sha256", "prerequisites_sha256")
            )
            and all(cls.identifier(context[key]) for key in ("session_id", "cell_id"))
            and cls.launch(context["origin_launch_id"])
        ):
            return None
        if stages is not None and not (
            context is not None
            and cls.exact(stages, {"workspace_sources", "static_camera_contract"})
            and all(item in cls.STATES for item in stages.values())
        ):
            return None
        publication = value["publication"]["status"]
        if (publication == "PENDING" and q is not None) or (
            publication == "HISTORICAL_HELD" and value["status"] != "HISTORICAL_HELD"
        ):
            return None
        if q is not None:
            if not (
                context is not None
                and cls.exact(
                    q,
                    {
                        "qualification_id",
                        "collection_launch_id",
                        "operator_id",
                        "original_subjects",
                        "receipt_sha256",
                        "assessment_sha256",
                        "software_checks",
                        "isolation",
                        "ownership",
                        "verdict",
                        "missing_requirements",
                        "review",
                    },
                )
                and type(q["qualification_id"]) is str
                and re.fullmatch(r"sourcequal-[0-9a-f]{32}", q["qualification_id"])
                is not None
                and cls.launch(q["collection_launch_id"])
                and cls.actor(q["operator_id"])
                and cls.exact(
                    q["original_subjects"],
                    {"receipt_sha256", "assessment_sha256", "review_sha256"},
                )
                and all(cls.digest(item) for item in q["original_subjects"].values())
                and cls.digest(q["receipt_sha256"])
                and cls.digest(q["assessment_sha256"])
                and q["verdict"] in ("PASS", "BLOCKED")
                and cls.codes(q["missing_requirements"], 32)
                and type(q["software_checks"]) is list
                and len(q["software_checks"]) == len(cls.CHECKS)
                and all(
                    cls.exact(row, {"check_id", "passed"})
                    and row["check_id"] == cls.CHECKS[index]
                    and type(row["passed"]) is bool
                    for index, row in enumerate(q["software_checks"])
                )
            ):
                return None
            isolation, owner, review = q["isolation"], q["ownership"], q["review"]
            if not (
                cls.exact(
                    isolation,
                    {
                        "state",
                        "statement",
                        "attachment_sha256",
                        "measurement_truth_verified",
                    },
                )
                and isolation["state"] in ("UNKNOWN", "OBSERVED_DISCONNECTED")
                and (
                    cls.string(isolation["statement"], 512)
                    or (
                        isolation["state"] == "UNKNOWN" and isolation["statement"] == ""
                    )
                )
                and isolation["statement"].strip() == isolation["statement"]
                and not any(
                    unicodedata.category(char).startswith("C")
                    for char in isolation["statement"]
                )
                and isolation["measurement_truth_verified"] is False
                and (
                    isolation["attachment_sha256"] is None
                    or cls.digest(isolation["attachment_sha256"])
                )
                and (
                    isolation["state"] != "OBSERVED_DISCONNECTED"
                    or isolation["attachment_sha256"] is not None
                )
                and cls.exact(owner, {"status", "report_sha256", "checks"})
                and owner["status"] in ("SOFTWARE_MECHANISMS_PASSED", "HELD")
                and cls.digest(owner["report_sha256"])
                and type(owner["checks"]) is list
                and len(owner["checks"]) == len(cls.OWNERSHIP)
                and all(
                    cls.exact(row, {"check_id", "passed", "provenance"})
                    and row["check_id"] == cls.OWNERSHIP[index]
                    and type(row["passed"]) is bool
                    and row["provenance"]
                    == (
                        "CONTROLLED_FAULT_INJECTION"
                        if index == 5
                        else "ACTUAL_HOST_MECHANISM"
                    )
                    for index, row in enumerate(owner["checks"])
                )
                and (
                    owner["status"] != "SOFTWARE_MECHANISMS_PASSED"
                    or all(row["passed"] for row in owner["checks"])
                )
            ):
                return None
            if q["verdict"] == "PASS" and (
                q["missing_requirements"]
                or not all(row["passed"] for row in q["software_checks"])
                or owner["status"] != "SOFTWARE_MECHANISMS_PASSED"
                or isolation["state"] != "OBSERVED_DISCONNECTED"
            ):
                return None
            if q["verdict"] == "BLOCKED" and not q["missing_requirements"]:
                return None
            if review is not None and not (
                cls.exact(
                    review,
                    {
                        "review_sha256",
                        "reviewer_id",
                        "review_launch_id",
                        "verdict",
                        "distinct_operator_labels",
                        "authenticated_independent_people",
                    },
                )
                and cls.digest(review["review_sha256"])
                and cls.actor(review["reviewer_id"])
                and review["reviewer_id"].casefold() != q["operator_id"].casefold()
                and cls.launch(review["review_launch_id"])
                and review["verdict"] == q["verdict"]
                and review["distinct_operator_labels"] is True
                and review["authenticated_independent_people"] is False
            ):
                return None
        status = value["status"]
        if (
            (status == "NOT_STARTED" and q is not None)
            or (status == "REVIEW_PENDING" and (q is None or q["review"] is not None))
            or (
                status == "REVIEWED_PASS"
                and (q is None or q["review"] is None or q["verdict"] != "PASS")
            )
            or (
                status == "REVIEWED_BLOCKED"
                and (q is None or q["review"] is None or q["verdict"] != "BLOCKED")
            )
        ):
            return None
        if (
            status in ("REVIEW_PENDING", "REVIEWED_PASS", "REVIEWED_BLOCKED")
            and publication != "CURRENT"
        ):
            return None
        if publication == "CURRENT":
            setup = (
                cls.setup(view.get("physical_camera_setup"))
                if type(view) is dict
                else None
            )
            if (
                setup is None
                or setup["publication"]["status"] != "CURRENT"
                or setup["session"]["verification"] is None
                or setup["prerequisites"] is None
                or context is None
                or stages is None
                or value["publication"]["operation_id"] is None
            ):
                return None
            binding, verified = (
                setup["session"]["binding"],
                setup["session"]["verification"],
            )
            if not (
                value["source_sha256"] == view.get("source_binding_sha256")
                and value["launch_session_id"]
                == view.get("session_id")
                == setup["launch_session_id"]
                and context["source_sha256"]
                == value["source_sha256"]
                == setup["source_sha256"]
                and context["session_id"] == binding["session_id"]
                and context["cell_id"] == binding["cell_id"]
                and context["origin_launch_id"] == binding["launch_id"]
                and context["header_sha256"] == verified["session"]["header_sha256"]
                and context["prerequisites_sha256"]
                == setup["prerequisites"]["evidence_sha256"]
                and stages["workspace_sources"]
                == setup["session"]["stages"][0]["state"]
                and stages["static_camera_contract"]
                == setup["session"]["stages"][1]["state"]
            ):
                return None
            if q is not None:
                original = _WorkspaceSourceDisplay.projection(
                    setup.get("source_workflow"), setup
                )
                if (
                    original is None
                    or any(
                        original[role] is None
                        for role in ("receipt", "assessment", "review")
                    )
                    or any(
                        q["original_subjects"][role + "_sha256"]
                        != original[role][role + "_sha256"]
                        for role in ("receipt", "assessment", "review")
                    )
                ):
                    return None
            if (
                (
                    status == "REVIEW_PENDING"
                    and stages["workspace_sources"] != "REVIEW_PENDING"
                )
                or (
                    status == "REVIEWED_PASS"
                    and (
                        stages["workspace_sources"] != "PASS"
                        or stages["static_camera_contract"]
                        not in ("PENDING", "WAITING_OPERATOR")
                    )
                )
                or (
                    status == "REVIEWED_BLOCKED"
                    and (
                        stages["workspace_sources"] != "BLOCKED"
                        or stages["static_camera_contract"] != "PENDING"
                    )
                )
            ):
                return None
        return value


class _StaticCameraOnboardingDisplay(_SourceReassessmentDisplay):
    """Closed cached design subjects, not original-file or stage verification."""

    ROLE_FLAGS = {
        "physical_authority",
        "hardware_qualified",
        "device_io_performed",
        "native_runtime_released",
    }
    ACTIONS = (
        "physical_static_contract_collect",
        "physical_static_contract_review",
        "physical_camera_receipt_begin",
    )
    CHECKS = (
        "base_software_ready",
        "readiness_and_architecture_select_static_primary",
        "architecture_has_zero_physical_authority",
        "secondary_camera_unselected",
        "automatic_camera_fallback_disabled",
        "camera_profile_has_zero_live_authority",
        "profile_and_support_identity_match",
        "profile_and_support_native_mode_match",
        "architecture_and_support_board_match",
        "architecture_and_support_required_view_match",
        "architecture_file_matches_source_binding",
        "camera_profile_file_matches_source_binding",
        "support_design_file_matches_source_binding",
        "support_locks_architecture_bytes",
        "support_locks_camera_profile_bytes",
        "every_support_dependency_matches_source_binding",
        "physical_qualification_holds_retained",
    )
    CONTEXT_KEYS = {
        "source_sha256",
        "session_id",
        "cell_id",
        "origin_launch_id",
        "header_sha256",
        "prerequisites_sha256",
    }
    BINDING_KEYS = CONTEXT_KEYS | {
        "contract_id",
        "collection_launch_id",
        "operator_id",
        "source_qualification",
        "static_request_event_sha256",
        "store_directory",
    }

    @classmethod
    def context(cls, value):
        return (
            cls.exact(value, cls.CONTEXT_KEYS)
            and all(
                cls.digest(value[key])
                for key in ("source_sha256", "header_sha256", "prerequisites_sha256")
            )
            and cls.launch(value["origin_launch_id"])
            and type(value["session_id"]) is str
            and re.fullmatch(r"physical-camera-[0-9a-f]{32}", value["session_id"])
            is not None
            and type(value["cell_id"]) is str
            and re.fullmatch(r"wizard-physical-camera-[0-9a-f]{16}", value["cell_id"])
            is not None
        )

    @classmethod
    def binding(cls, value):
        return (
            cls.exact(value, cls.BINDING_KEYS)
            and cls.context({key: value[key] for key in cls.CONTEXT_KEYS})
            and type(value["contract_id"]) is str
            and re.fullmatch(r"staticcontract-[0-9a-f]{32}", value["contract_id"])
            is not None
            and cls.launch(value["collection_launch_id"])
            and cls.actor(value["operator_id"])
            and cls.digest(value["static_request_event_sha256"])
            and cls.string(value["store_directory"], 16384)
            and len(value["store_directory"]) <= 4096
            and cls.exact(
                value["source_qualification"], {"receipt", "assessment", "review"}
            )
            and all(cls.digest(item) for item in value["source_qualification"].values())
        )

    @staticmethod
    def positive(value):
        return (
            type(value) in (int, float)
            and math.isfinite(value)
            and 0 < value <= 1000000
        )

    @classmethod
    def check_rows(cls, value):
        return (
            type(value) is list
            and len(value) == len(cls.CHECKS)
            and all(
                cls.exact(row, {"check_id", "passed"})
                and row["check_id"] == cls.CHECKS[index]
                and type(row["passed"]) is bool
                for index, row in enumerate(value)
            )
        )

    @classmethod
    def roles(cls, contract, context):
        if not (
            cls.exact(
                contract, {"contract_id", "state", "receipt", "assessment", "review"}
            )
            and type(contract["contract_id"]) is str
            and re.fullmatch(r"staticcontract-[0-9a-f]{32}", contract["contract_id"])
            is not None
            and contract["state"]
            in (
                "INCOMPLETE",
                "ASSESSMENT_RETAINED_NOT_COMMITTED",
                "REVIEW_PENDING",
                "REVIEW_RETAINED_NOT_COMMITTED",
                "REVIEWED_PASS",
                "REVIEWED_BLOCKED",
            )
        ):
            return False
        receipt, assessment, review = (
            contract[key] for key in ("receipt", "assessment", "review")
        )
        for item in (receipt, assessment, review):
            if item is not None and not (
                type(item) is dict
                and cls.binding(item.get("binding"))
                and item["binding"]["contract_id"] == contract["contract_id"]
                and all(
                    item["binding"][key] == context[key] for key in cls.CONTEXT_KEYS
                )
                and all(item.get(key) is False for key in cls.ROLE_FLAGS)
                and len(
                    json.dumps(item, ensure_ascii=True, separators=(",", ":")).encode()
                )
                <= 24576
            ):
                return False
        if receipt is not None:
            if not (
                cls.exact(
                    receipt,
                    {
                        "schema",
                        "binding",
                        "receipt_sha256",
                        "status",
                        "checks",
                        "design",
                        "blockers",
                        "source_file_count",
                        "source_bytes",
                    }
                    | cls.ROLE_FLAGS,
                )
                and receipt["schema"]
                == "rocell.static_camera_contract_receipt_summary.v1"
                and receipt["status"] == "DESIGN_INPUTS_COLLECTED"
                and cls.digest(receipt["receipt_sha256"])
                and cls.check_rows(receipt["checks"])
                and type(receipt["source_file_count"]) is int
                and receipt["source_file_count"] == 5
                and cls.integer(receipt["source_bytes"], 1, 131072)
                and cls.exact(
                    receipt["blockers"], {"architecture", "profile", "support"}
                )
                and all(
                    type(rows) is list
                    and len(rows) <= 32
                    and all(cls.string(row, 4096) for row in rows)
                    for rows in receipt["blockers"].values()
                )
            ):
                return False
            design = receipt["design"]
            if not (
                cls.exact(
                    design,
                    {
                        "camera_model",
                        "sensor",
                        "lens_mount",
                        "focal_length_mm",
                        "board_size_mm",
                        "required_view_mm",
                        "nominal_entrance_pupil_z_mm",
                        "published_mode",
                        "value_provenance",
                    },
                )
                and all(
                    cls.string(design[key], 512)
                    for key in ("camera_model", "sensor", "lens_mount")
                )
                and cls.positive(design["focal_length_mm"])
                and cls.positive(design["nominal_entrance_pupil_z_mm"])
                and design["value_provenance"] == "DESIGN_NOT_MEASURED"
                and all(
                    type(design[key]) is list
                    and len(design[key]) == count
                    and all(cls.positive(item) for item in design[key])
                    for key, count in (("board_size_mm", 3), ("required_view_mm", 2))
                )
            ):
                return False
            mode = design["published_mode"]
            if mode is not None and not (
                cls.exact(
                    mode,
                    {
                        "host_bus",
                        "width_px",
                        "height_px",
                        "maximum_fps",
                        "pixel_format",
                        "evidence_state",
                    },
                )
                and all(
                    cls.string(mode[key], 128)
                    for key in ("host_bus", "pixel_format", "evidence_state")
                )
                and cls.integer(mode["width_px"], 1, 100000)
                and cls.integer(mode["height_px"], 1, 100000)
                and cls.positive(mode["maximum_fps"])
            ):
                return False
        if assessment is not None:
            if not (
                receipt is not None
                and cls.exact(
                    assessment,
                    {
                        "schema",
                        "binding",
                        "receipt_sha256",
                        "assessment_sha256",
                        "status",
                        "verdict",
                        "checks",
                        "missing_requirements",
                    }
                    | cls.ROLE_FLAGS,
                )
                and assessment["schema"]
                == "rocell.static_camera_contract_assessment_summary.v1"
                and assessment["status"] == "ASSESSED"
                and cls.digest(assessment["assessment_sha256"])
                and assessment["receipt_sha256"] == receipt["receipt_sha256"]
                and assessment["binding"] == receipt["binding"]
                and cls.check_rows(assessment["checks"])
                and assessment["checks"] == receipt["checks"]
                and assessment["missing_requirements"]
                == [
                    row["check_id"] for row in assessment["checks"] if not row["passed"]
                ]
                and assessment["verdict"]
                == ("BLOCKED" if assessment["missing_requirements"] else "PASS")
            ):
                return False
        if review is not None:
            if not (
                assessment is not None
                and cls.exact(
                    review,
                    {
                        "schema",
                        "binding",
                        "receipt_sha256",
                        "assessment_sha256",
                        "review_sha256",
                        "status",
                        "verdict",
                        "reviewer_id",
                        "review_launch_id",
                        "reviewed_at_ns",
                        "procedure_complete",
                    }
                    | cls.ROLE_FLAGS,
                )
                and review["schema"]
                == "rocell.static_camera_contract_review_summary.v1"
                and review["status"] == "REVIEW_RECORDED"
                and cls.digest(review["review_sha256"])
                and review["receipt_sha256"] == receipt["receipt_sha256"]
                and review["assessment_sha256"] == assessment["assessment_sha256"]
                and review["binding"] == receipt["binding"]
                and review["verdict"] == assessment["verdict"]
                and cls.actor(review["reviewer_id"])
                and review["reviewer_id"].casefold()
                != receipt["binding"]["operator_id"].casefold()
                and cls.launch(review["review_launch_id"])
                and cls.integer(review["reviewed_at_ns"], 1, 2**63 - 1)
                and review["procedure_complete"] is True
            ):
                return False
        state = contract["state"]
        return not (
            (
                state in ("REVIEW_PENDING", "ASSESSMENT_RETAINED_NOT_COMMITTED")
                and (assessment is None or review is not None)
            )
            or (
                state
                in (
                    "REVIEWED_PASS",
                    "REVIEWED_BLOCKED",
                    "REVIEW_RETAINED_NOT_COMMITTED",
                )
                and review is None
            )
            or (state == "REVIEWED_PASS" and review["verdict"] != "PASS")
            or (state == "REVIEWED_BLOCKED" and review["verdict"] != "BLOCKED")
        )

    @classmethod
    def projection(cls, value: Any, view: Any) -> dict[str, Any] | None:
        if not (
            cls.exact(
                value,
                {
                    "schema",
                    "source_sha256",
                    "launch_session_id",
                    "original_context",
                    "publication",
                    "status",
                    "stage_states",
                    "contract",
                    "camera_receipt_entry",
                    "next_action",
                    "meaning",
                }
                | cls.FLAGS,
            )
            and value["schema"] == "rocell.wizard_static_camera_onboarding.v1"
            and cls.digest(value["source_sha256"])
            and cls.launch(value["launch_session_id"])
            and all(value[key] is False for key in cls.FLAGS)
            and cls.string(value["meaning"], 512)
            and value["status"]
            in (
                "NOT_STARTED",
                "REVIEW_PENDING",
                "REVIEWED_PASS",
                "REVIEWED_BLOCKED",
                "INCOMPLETE_HELD",
                "HISTORICAL_HELD",
            )
            and cls.exact(value["publication"], {"status", "operation_id"})
            and value["publication"]["status"]
            in ("NOT_PUBLISHED", "PENDING", "CURRENT", "HISTORICAL_HELD")
            and (
                value["publication"]["operation_id"] is None
                or cls.identifier(value["publication"]["operation_id"])
            )
            and (value["next_action"] is None or value["next_action"] in cls.ACTIONS)
            and (
                value["camera_receipt_entry"] is None
                or cls.digest(value["camera_receipt_entry"])
            )
        ):
            return None
        context, stages, contract = (
            value["original_context"],
            value["stage_states"],
            value["contract"],
        )
        publication = value["publication"]["status"]
        if (
            (context is not None and not cls.context(context))
            or (
                stages is not None
                and not (
                    cls.exact(
                        stages,
                        {
                            "workspace_sources",
                            "static_camera_contract",
                            "camera_receipt",
                        },
                    )
                    and all(item in cls.STATES for item in stages.values())
                )
            )
            or (
                publication == "PENDING"
                and (contract is not None or value["camera_receipt_entry"] is not None)
            )
            or (
                publication == "HISTORICAL_HELD"
                and value["status"] != "HISTORICAL_HELD"
                and not (
                    value["status"] == "NOT_STARTED"
                    and contract is None
                    and value["camera_receipt_entry"] is None
                    and value["next_action"] is None
                )
            )
            or (
                contract is not None
                and (context is None or not cls.roles(contract, context))
            )
        ):
            return None
        if (value["status"] == "NOT_STARTED" and contract is not None) or (
            value["status"] in ("REVIEW_PENDING", "REVIEWED_PASS", "REVIEWED_BLOCKED")
            and (
                contract is None
                or contract["state"] != value["status"]
                or publication != "CURRENT"
            )
        ):
            return None
        if publication == "CURRENT":
            setup = cls.setup(view.get("physical_camera_setup"))
            if (
                value["status"] == "NOT_STARTED"
                and contract is None
                and value["camera_receipt_entry"] is None
                and value["next_action"] is None
            ):
                # Storage-only publication before any design subject exists.
                if (
                    not setup
                    or setup["publication"]["status"] != "CURRENT"
                    or not setup["session"]["verification"]
                    or stages is None
                    or value["publication"]["operation_id"] is None
                    or value["source_sha256"] != view.get("source_binding_sha256")
                    or value["source_sha256"] != setup["source_sha256"]
                    or value["launch_session_id"] != view.get("session_id")
                    or value["launch_session_id"] != setup["launch_session_id"]
                    or any(
                        stages[key] != setup["session"]["stages"][i]["state"]
                        for i, key in enumerate(
                            (
                                "workspace_sources",
                                "static_camera_contract",
                                "camera_receipt",
                            )
                        )
                    )
                ):
                    return None
                if context is None:
                    return value if setup["prerequisites"] is None else None
                bound = setup["session"]["binding"]
                if (
                    not setup["prerequisites"]
                    or context["source_sha256"] != value["source_sha256"]
                    or any(
                        context[key] != bound[key] for key in ("session_id", "cell_id")
                    )
                    or context["origin_launch_id"] != bound["launch_id"]
                    or context["header_sha256"]
                    != setup["session"]["verification"]["session"]["header_sha256"]
                    or context["prerequisites_sha256"]
                    != setup["prerequisites"]["evidence_sha256"]
                ):
                    return None
                return value
            if (
                not setup
                or setup["publication"]["status"] != "CURRENT"
                or not setup["session"]["verification"]
                or not setup["prerequisites"]
                or context is None
                or stages is None
            ):
                return None
            bound, verification = (
                setup["session"]["binding"],
                setup["session"]["verification"],
            )
            if (
                value["publication"]["operation_id"] is None
                or value["source_sha256"] != view.get("source_binding_sha256")
                or value["launch_session_id"] != view.get("session_id")
                or value["launch_session_id"] != setup["launch_session_id"]
                or context["source_sha256"] != value["source_sha256"]
                or context["source_sha256"] != setup["source_sha256"]
                or any(context[key] != bound[key] for key in ("session_id", "cell_id"))
                or context["origin_launch_id"] != bound["launch_id"]
                or context["header_sha256"] != verification["session"]["header_sha256"]
                or context["prerequisites_sha256"]
                != setup["prerequisites"]["evidence_sha256"]
                or any(
                    stages[key] != setup["session"]["stages"][index]["state"]
                    for index, key in enumerate(
                        (
                            "workspace_sources",
                            "static_camera_contract",
                            "camera_receipt",
                        )
                    )
                )
                or stages["workspace_sources"] != "PASS"
            ):
                return None
            if contract is not None and contract["receipt"] is not None:
                source = _SourceReassessmentDisplay.projection(
                    view.get("source_reassessment"), view
                )
                q = None if source is None else source["qualification"]
                binding = contract["receipt"]["binding"]
                if (
                    not q
                    or not q["review"]
                    or q["verdict"] != "PASS"
                    or binding["store_directory"] != bound["directory"]
                    or any(
                        binding["source_qualification"][role] != q[role + "_sha256"]
                        for role in ("receipt", "assessment")
                    )
                    or binding["source_qualification"]["review"]
                    != q["review"]["review_sha256"]
                ):
                    return None
            if (
                (
                    value["status"] == "REVIEW_PENDING"
                    and stages["static_camera_contract"] != "REVIEW_PENDING"
                )
                or (
                    value["status"] == "REVIEWED_PASS"
                    and (
                        stages["static_camera_contract"] != "PASS"
                        or stages["camera_receipt"]
                        not in ("PENDING", "WAITING_OPERATOR")
                    )
                )
                or (
                    value["status"] == "REVIEWED_BLOCKED"
                    and (
                        stages["static_camera_contract"] != "BLOCKED"
                        or stages["camera_receipt"] != "PENDING"
                    )
                )
                or (
                    (stages["camera_receipt"] == "WAITING_OPERATOR")
                    != (value["camera_receipt_entry"] is not None)
                )
            ):
                return None
        return value


class _PhysicalIntakeEvidenceDisplay(_PhysicalSetupDisplay):
    """Closed cached projections; no attachment reads or subject reconstruction."""

    FLAGS = {
        "physical_authority",
        "hardware_qualified",
        "canonical_stage_pass",
        "device_io_performed",
        "measurement_truth_verified",
        "authenticated_operator_identity",
    }
    CONTEXT = {
        "source_sha256",
        "session_id",
        "cell_id",
        "origin_launch_id",
        "header_sha256",
        "prerequisites_sha256",
    }
    BINDING = CONTEXT | {
        "source_binding_sha256",
        "submission_launch_id",
        "notebook_sha256",
    }
    RECORDS = tuple(
        "INT-" + x
        for x in (
            "001",
            "002",
            "003",
            "004",
            "005",
            "006",
            "007",
            "008",
            "009",
            "017",
            "019",
            "020",
            "021",
            "022",
            "023",
            "024",
        )
    )
    MEDIA = {
        "txt": "text/plain",
        "json": "application/json",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "pdf": "application/pdf",
    }
    ISSUES = tuple(
        "INTAKE_INBOX_" + x
        for x in (
            "BUSY",
            "INVALID",
            "LIMIT",
            "UNSAFE_FILE",
            "FILE_LIMIT",
            "FILE_TYPE",
            "CONTENT",
            "CHANGED",
            "STALE_CHOICE",
            "SOURCE_CHANGED",
            "CANCELLED",
            "DEADLINE",
            "READ_FAILED",
        )
    )

    @staticmethod
    def token(value: Any, pattern: str = r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}") -> bool:
        return type(value) is str and re.fullmatch(pattern, value) is not None

    @classmethod
    def text(cls, value: Any, maximum: int) -> bool:
        return (
            cls.string(value, maximum)
            and value.strip() == value
            and not any(unicodedata.category(c).startswith("C") for c in value)
        )

    @classmethod
    def basename(cls, value: Any) -> bool:
        return cls.token(
            value, r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}"
        ) and not value.endswith(".")

    @classmethod
    def attachment(cls, value: Any, discovered: bool) -> bool:
        key = "choice_id" if discovered else "evidence_id"
        return (
            cls.exact(
                value,
                {key, "basename", "media_type", "payload_bytes", "payload_sha256"},
            )
            and cls.token(
                value[key],
                (
                    r"intake-file-[0-9a-f]{32}"
                    if discovered
                    else r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}"
                ),
            )
            and cls.basename(value["basename"])
            and value["media_type"]
            == cls.MEDIA.get(value["basename"].rsplit(".", 1)[-1].lower())
            and cls.digest(value["payload_sha256"])
            and cls.integer(
                value["payload_bytes"], 1, (2 if discovered else 4) * 1024 * 1024
            )
        )

    @classmethod
    def bound(cls, value: Any, keys: set[str]) -> bool:
        return cls.exact(value, keys) and all(
            cls.digest(value[k]) if k.endswith("sha256") else cls.token(value[k])
            for k in keys
        )

    @classmethod
    def no_authority(cls, value: dict[str, Any]) -> bool:
        return all(value[k] is False for k in cls.FLAGS) and cls.text(
            value["meaning"], 512
        )

    @classmethod
    def collection(cls, value: Any, context: Any, count: int) -> bool:
        same = _PhysicalIntakeDisplay.same_question
        if not (
            context is not None
            and cls.exact(
                value, {"collection_id", "state", "submission", "assessment", "review"}
            )
            and cls.token(value["collection_id"], r"intake-[0-9a-f]{32}")
            and value["state"]
            in (
                "INCOMPLETE",
                "REVIEW_PENDING",
                "REVIEW_RETAINED_NOT_COMMITTED",
                "REVIEWED_BLOCKED",
            )
            and count >= 1
        ):
            return False
        s, a, r = value["submission"], value["assessment"], value["review"]
        if s is not None:
            if not (
                cls.exact(
                    s,
                    {
                        "schema",
                        "submission_sha256",
                        "binding",
                        "collection_id",
                        "sequence",
                        "predecessor_submission_sha256",
                        "operator_id",
                        "notebook_revision",
                        "stage",
                        "observation_owner_stage",
                        "rows",
                        "attachments",
                        "coverage",
                        "meaning",
                    }
                    | cls.FLAGS,
                )
                and s["schema"]
                == "rocell.physical_passive_intake_submission_summary.v1"
                and cls.digest(s["submission_sha256"])
                and cls.bound(s["binding"], cls.BINDING)
                and all(s["binding"][k] == context[k] for k in cls.CONTEXT)
                and s["collection_id"] == value["collection_id"]
                and cls.integer(s["sequence"], 1, 8)
                and s["sequence"] == count
                and (
                    s["predecessor_submission_sha256"] is None
                    if s["sequence"] == 1
                    else cls.digest(s["predecessor_submission_sha256"])
                )
                and cls.token(s["operator_id"], r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
                and cls.integer(s["notebook_revision"], 1, 128)
                and s["stage"] == "workspace_sources"
                and s["observation_owner_stage"] == "camera_receipt"
                and cls.no_authority(s)
                and type(s["rows"]) is list
                and len(s["rows"]) == 16
                and type(s["attachments"]) is list
                and len(s["attachments"]) <= 16
                and all(cls.attachment(x, False) for x in s["attachments"])
                and len({x["evidence_id"] for x in s["attachments"]})
                == len(s["attachments"])
            ):
                return False
            attached, unknown = set(), []
            observed = linked = 0
            for record_id, row in zip(cls.RECORDS, s["rows"]):
                deferred = record_id == "INT-005"
                if not (
                    cls.exact(
                        row,
                        {
                            "record_id",
                            "measurement",
                            "unit",
                            "status",
                            "observed_value",
                            "method",
                            "attachment_evidence_id",
                            "acceptance_status",
                            "acceptance_owner_stage",
                        },
                    )
                    and row["record_id"] == record_id
                    and cls.text(row["measurement"], 4096)
                    and (row["unit"] == "" or cls.text(row["unit"], 4096))
                    and row["status"] in ("OBSERVED", "UNKNOWN")
                    and cls.text(row["observed_value"], 256)
                    and cls.text(row["method"], 512)
                    and row["acceptance_status"]
                    == ("DEFERRED_LIMIT" if deferred else "NOT_ASSESSED")
                    and row["acceptance_owner_stage"]
                    == ("noncontact_acceptance" if deferred else "camera_receipt")
                ):
                    return False
                if row["attachment_evidence_id"] is not None:
                    if not any(
                        x["evidence_id"] == row["attachment_evidence_id"]
                        for x in s["attachments"]
                    ):
                        return False
                    attached.add(row["attachment_evidence_id"])
                    linked += 1
                if row["status"] == "OBSERVED":
                    if row["attachment_evidence_id"] is None or (
                        row["unit"] in ("mm", "g")
                        and (
                            re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", row["observed_value"])
                            is None
                            or (
                                not deferred
                                and re.search(r"[1-9]", row["observed_value"]) is None
                            )
                        )
                    ):
                        return False
                    observed += 1
                else:
                    unknown.append(record_id)
            expected = {
                "total": 16,
                "observed": observed,
                "unknown": 16 - observed,
                "attached_rows": linked,
                "attachment_count": len(s["attachments"]),
                "attachment_bytes": sum(x["payload_bytes"] for x in s["attachments"]),
            }
            if (
                not same(s["coverage"], expected)
                or expected["attachment_bytes"] > 4 * 1024 * 1024
                or len(attached) != len(s["attachments"])
            ):
                return False
            if a is not None and not (
                cls.exact(
                    a,
                    {
                        "schema",
                        "assessment_sha256",
                        "submission_sha256",
                        "binding",
                        "collection_id",
                        "status",
                        "observation_completeness",
                        "unknown_record_ids",
                        "coverage",
                        "physical_readiness",
                        "meaning",
                    }
                    | cls.FLAGS,
                )
                and a["schema"]
                == "rocell.physical_passive_intake_assessment_summary.v1"
                and cls.digest(a["assessment_sha256"])
                and a["submission_sha256"] == s["submission_sha256"]
                and same(a["binding"], s["binding"])
                and a["collection_id"] == value["collection_id"]
                and a["status"] == "STRUCTURE_AND_REFERENCES_VALID"
                and a["observation_completeness"]
                == ("UNKNOWN_ROWS_REMAIN" if unknown else "ALL_ROWS_OBSERVED")
                and same(a["unknown_record_ids"], unknown)
                and same(a["coverage"], expected)
                and a["physical_readiness"] is False
                and cls.no_authority(a)
            ):
                return False
            if r is not None and not (
                a is not None
                and cls.exact(
                    r,
                    {
                        "schema",
                        "review_sha256",
                        "binding",
                        "collection_id",
                        "submission_sha256",
                        "assessment_sha256",
                        "reviewer_id",
                        "review_launch_id",
                        "decision",
                        "status",
                        "distinct_operator_labels",
                        "authenticated_independent_people",
                        "meaning",
                    }
                    | cls.FLAGS,
                )
                and r["schema"] == "rocell.physical_passive_intake_review_summary.v1"
                and cls.digest(r["review_sha256"])
                and same(r["binding"], s["binding"])
                and r["collection_id"] == value["collection_id"]
                and r["submission_sha256"] == s["submission_sha256"]
                and r["assessment_sha256"] == a["assessment_sha256"]
                and cls.token(r["reviewer_id"], r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
                and r["reviewer_id"].casefold() != s["operator_id"].casefold()
                and cls.token(r["review_launch_id"])
                and r["decision"] in ("ACKNOWLEDGE_FOR_LATER_STAGE_REVIEW", "REJECT")
                and r["status"]
                == (
                    "REJECTED"
                    if r["decision"] == "REJECT"
                    else "ACKNOWLEDGED_FOR_LATER_STAGE_REVIEW"
                )
                and r["distinct_operator_labels"] is True
                and r["authenticated_independent_people"] is False
                and cls.no_authority(r)
            ):
                return False
        elif a is not None or r is not None:
            return False
        return not (
            (value["state"] != "INCOMPLETE" and (s is None or a is None))
            or (value["state"] == "REVIEW_PENDING" and r is not None)
            or (
                value["state"] in ("REVIEW_RETAINED_NOT_COMMITTED", "REVIEWED_BLOCKED")
                and r is None
            )
        )

    @classmethod
    def projection(cls, value: Any, view: dict[str, Any]) -> dict[str, Any] | None:
        if not (
            cls.exact(
                value,
                {
                    "schema",
                    "source_sha256",
                    "launch_session_id",
                    "original_context",
                    "publication",
                    "status",
                    "discovery",
                    "collection",
                    "collection_count",
                    "physical_authority",
                    "hardware_qualified",
                    "meaning",
                },
            )
            and value["schema"] == "rocell.wizard_physical_intake_evidence.v1"
            and cls.digest(value["source_sha256"])
            and cls.token(value["launch_session_id"])
            and value["physical_authority"] is False
            and value["hardware_qualified"] is False
            and cls.text(value["meaning"], 512)
            and value["status"]
            in (
                "NOT_STARTED",
                "DISCOVERED",
                "SUBMITTED_REVIEW_PENDING",
                "REVIEWED",
                "INCOMPLETE_HELD",
                "HISTORICAL_HELD",
            )
            and cls.integer(value["collection_count"], 0, 8)
            and cls.exact(value["publication"], {"status", "operation_id"})
            and value["publication"]["status"]
            in ("NOT_PUBLISHED", "PENDING", "CURRENT", "HISTORICAL_HELD")
            and (
                value["publication"]["operation_id"] is None
                or cls.token(value["publication"]["operation_id"])
            )
        ):
            return None
        context, d, c = (
            value["original_context"],
            value["discovery"],
            value["collection"],
        )
        if context is not None and not cls.bound(context, cls.CONTEXT):
            return None
        if not (
            cls.exact(
                d,
                {
                    "schema",
                    "status",
                    "directory",
                    "source_sha256",
                    "launch_session_id",
                    "discovery_sha256",
                    "files",
                    "issues",
                    "physical_authority",
                    "device_io_performed",
                },
            )
            and d["schema"] == "rocell.physical_intake_inbox.v1"
            and d["status"] in ("NOT_DISCOVERED", "READY", "HELD")
            and cls.string(d["directory"], 4096)
            and re.match(r"^(?:[A-Za-z]:[\\/]|/)", d["directory"]) is not None
            and ".." not in d["directory"].replace("\\", "/").split("/")
            and d["directory"]
            .replace("\\", "/")
            .endswith("/software/runs/physical-intake-inbox")
            and d["source_sha256"] == value["source_sha256"]
            and d["launch_session_id"] == value["launch_session_id"]
            and d["physical_authority"] is False
            and d["device_io_performed"] is False
            and type(d["files"]) is list
            and len(d["files"]) <= 32
            and all(cls.attachment(x, True) for x in d["files"])
            and len({x["choice_id"] for x in d["files"]}) == len(d["files"])
            and len({x["basename"] for x in d["files"]}) == len(d["files"])
            and sum(x["payload_bytes"] for x in d["files"]) <= 16 * 1024 * 1024
            and type(d["issues"]) is list
            and len(d["issues"]) <= 33
            and all(
                cls.exact(x, {"code", "basename"})
                and x["code"] in cls.ISSUES
                and (x["basename"] is None or cls.basename(x["basename"]))
                for x in d["issues"]
            )
            and (
                cls.digest(d["discovery_sha256"])
                if d["status"] == "READY"
                else d["discovery_sha256"] is None and not d["files"]
            )
            and (d["status"] != "NOT_DISCOVERED" or not d["issues"])
        ):
            return None
        if value["publication"]["status"] == "PENDING":
            return (
                value
                if c is None
                and d["status"] == "NOT_DISCOVERED"
                and value["status"] in ("NOT_STARTED", "HISTORICAL_HELD")
                else None
            )
        if c is not None and not cls.collection(c, context, value["collection_count"]):
            return None
        if (
            (
                value["status"] == "NOT_STARTED"
                and (
                    c is not None
                    or value["collection_count"] != 0
                    or (
                        value["publication"]["status"] != "HISTORICAL_HELD"
                        and d["status"] != "NOT_DISCOVERED"
                    )
                )
            )
            or (value["status"] == "DISCOVERED" and d["status"] != "READY")
            or (
                value["status"] == "SUBMITTED_REVIEW_PENDING"
                and (c is None or c["state"] != "REVIEW_PENDING")
            )
            or (
                value["status"] == "REVIEWED"
                and (c is None or c["state"] != "REVIEWED_BLOCKED")
            )
            or (
                value["publication"]["status"] == "HISTORICAL_HELD"
                and value["status"] not in ("HISTORICAL_HELD", "NOT_STARTED")
            )
        ):
            return None
        if value["publication"]["status"] == "CURRENT":
            setup = cls.setup(view.get("physical_camera_setup"))
            if not (
                value["source_sha256"] == view.get("source_binding_sha256")
                and value["launch_session_id"] == view.get("session_id")
                and setup is not None
                and setup["publication"]["status"] == "CURRENT"
                and setup["prerequisites"] is not None
                and setup["session"]["verification"] is not None
                and context is not None
            ):
                return None
            b, verified = setup["session"]["binding"], setup["session"]["verification"]
            if not (
                context["source_sha256"] == setup["source_sha256"]
                and context["session_id"] == b["session_id"]
                and context["cell_id"] == b["cell_id"]
                and context["origin_launch_id"] == b["launch_id"]
                and context["header_sha256"] == verified["session"]["header_sha256"]
                and context["prerequisites_sha256"]
                == setup["prerequisites"]["evidence_sha256"]
            ):
                return None
            if c is not None and c["submission"] is not None:
                if (
                    c["submission"]["binding"]["source_binding_sha256"]
                    != verified["cell"]["source_binding_sha256"]
                ):
                    return None
                questions = next(
                    x["intake_rows"]
                    for x in setup["prerequisites"]["stages"]
                    if x["stage"] == "camera_receipt"
                )
                if not all(
                    row["measurement"] == q["measurement"] and row["unit"] == q["unit"]
                    for row, q in zip(c["submission"]["rows"], questions)
                ):
                    return None
            if c is not None:
                source = _WorkspaceSourceDisplay.projection(
                    setup.get("source_workflow"), setup
                )
                canonical = {
                    "INCOMPLETE": "WAITING_OPERATOR",
                    "REVIEW_PENDING": "REVIEW_PENDING",
                    "REVIEW_RETAINED_NOT_COMMITTED": "REVIEW_PENDING",
                    "REVIEWED_BLOCKED": "BLOCKED",
                }
                if (
                    source is None
                    or type(source.get("supplementary")) is not dict
                    or source["supplementary"]["collection_id"] != c["collection_id"]
                    or source["supplementary"]["state"] != canonical[c["state"]]
                ):
                    return None
        return value


class _PhysicalIntakeDisplay(_PhysicalSetupDisplay):
    """Validate cached drafts against the exact currently published questions."""

    @classmethod
    def same_question(cls, left: Any, right: Any) -> bool:
        if type(left) is not type(right):
            return False
        if type(left) is dict:
            return left.keys() == right.keys() and all(
                cls.same_question(left[key], right[key]) for key in left
            )
        if type(left) is list:
            return len(left) == len(right) and all(
                cls.same_question(a, b) for a, b in zip(left, right)
            )
        return left == right

    @classmethod
    def entry_text(cls, value: Any, maximum: int) -> bool:
        return (
            cls.string(value, maximum)
            and value.strip() == value
            and not any(
                unicodedata.category(character).startswith("C") for character in value
            )
        )

    @classmethod
    def validate(cls, value: Any, setup_value: Any) -> dict[str, Any] | None:
        if not (
            cls.exact(
                value,
                {
                    "schema",
                    "status",
                    "notebook",
                    "physical_authority",
                    "hardware_qualified",
                    "meaning",
                },
            )
            and value["schema"] == "rocell.wizard_physical_intake.v1"
            and value["status"] in ("NOT_STARTED", "CURRENT_DRAFT", "HISTORICAL_HELD")
            and value["physical_authority"] is False
            and value["hardware_qualified"] is False
            and cls.string(value["meaning"], 512)
        ):
            return None
        if value["status"] != "CURRENT_DRAFT":
            return value if value["notebook"] is None else None
        setup = cls.setup(setup_value)
        n = value["notebook"]
        if not (
            setup is not None
            and setup["publication"]["status"] == "CURRENT"
            and setup["prerequisites"] is not None
            and cls.exact(
                n,
                {
                    "schema",
                    "binding",
                    "revision",
                    "previous_sha256",
                    "rows",
                    "coverage",
                    "physical_authority",
                    "hardware_qualified",
                    "canonical_stage_pass",
                    "device_io_performed",
                    "attachment_bytes_verified",
                    "meaning",
                    "snapshot_sha256",
                },
            )
            and n["schema"] == "rocell.physical_intake_notebook.v1"
            and cls.integer(n["revision"], 0, 128)
            and cls.digest(n["snapshot_sha256"])
            and (
                n["previous_sha256"] is None
                if n["revision"] == 0
                else cls.digest(n["previous_sha256"])
                and n["previous_sha256"] != "0" * 64
            )
            and all(
                n[key] is False
                for key in (
                    "physical_authority",
                    "hardware_qualified",
                    "canonical_stage_pass",
                    "device_io_performed",
                    "attachment_bytes_verified",
                )
            )
            and cls.string(n["meaning"], 512)
            and cls.exact(
                n["binding"],
                {
                    "source_sha256",
                    "session_id",
                    "origin_launch_id",
                    "launch_session_id",
                    "prerequisites_sha256",
                },
            )
        ):
            return None
        original = setup["session"]["binding"]
        if n["binding"] != {
            "source_sha256": setup["source_sha256"],
            "session_id": original["session_id"],
            "origin_launch_id": original["launch_id"],
            "launch_session_id": setup["launch_session_id"],
            "prerequisites_sha256": setup["prerequisites"]["evidence_sha256"],
        }:
            return None
        questions = next(
            stage
            for stage in setup["prerequisites"]["stages"]
            if stage["stage"] == "camera_receipt"
        )["intake_rows"]
        if not (
            type(n["rows"]) is list
            and len(n["rows"]) == 16
            and cls.exact(n["coverage"], {"total", "observed", "unknown", "unrecorded"})
            and all(cls.integer(number, 0, 16) for number in n["coverage"].values())
        ):
            return None
        observed = unknown = 0
        for row, question in zip(n["rows"], questions):
            if not cls.exact(row, set(question)) or not cls.same_question(
                {key: item for key, item in row.items() if key != "observation"},
                {key: item for key, item in question.items() if key != "observation"},
            ):
                return None
            observation = row["observation"]
            if observation is None:
                continue
            if not (
                cls.exact(
                    observation,
                    {
                        "status",
                        "observed_value",
                        "method",
                        "evidence_note",
                        "operator_id",
                        "recorded_at_ns",
                    },
                )
                and observation["status"] in ("OBSERVED", "UNKNOWN")
                and all(
                    cls.entry_text(observation[key], maximum)
                    for key, maximum in (
                        ("observed_value", 256),
                        ("method", 512),
                        ("evidence_note", 1024),
                        ("operator_id", 64),
                    )
                )
                and cls.integer(observation["recorded_at_ns"], 1, 2**63 - 1)
            ):
                return None
            if observation["status"] == "OBSERVED":
                if row["unit"] in ("mm", "g") and (
                    re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", observation["observed_value"])
                    is None
                    or (
                        row["record_id"] != "INT-005"
                        and not re.search(r"[1-9]", observation["observed_value"])
                    )
                ):
                    return None
                observed += 1
            else:
                unknown += 1
        if (
            n["coverage"]
            != {
                "total": 16,
                "observed": observed,
                "unknown": unknown,
                "unrecorded": 16 - observed - unknown,
            }
            or observed + unknown > n["revision"]
            or (n["revision"] > 0 and observed + unknown == 0)
        ):
            return None
        payload = {key: item for key, item in n.items() if key != "snapshot_sha256"}
        if len(json.dumps(payload, ensure_ascii=True, separators=(",", ":"))) > 65536:
            return None
        return value


class _ReceivedCameraDisplay(_PhysicalIntakeDisplay):
    """Cached display joins only: no evidence loading, acceptance or dispatch."""

    FLAGS = {
        "physical_authority",
        "hardware_qualified",
        "native_release_allowed",
        "device_io_performed",
    }
    BASE_FLAGS = {
        "physical_authority",
        "hardware_qualified",
        "canonical_stage_pass",
        "device_io_performed",
        "attachment_bytes_verified",
    }
    ROLE_FLAGS = BASE_FLAGS | {
        "installation_qualified",
        "native_runtime_released",
        "measurement_truth_verified",
        "authenticated_operator_identity",
    }
    RECORDS = tuple(
        "INT-" + item
        for item in "001 002 003 004 005 006 007 008 009 017 019 020 021 022 023 024".split()
    )
    RECEIVED_STAGES = (
        "workspace_sources",
        "static_camera_contract",
        "camera_receipt",
        "camera_identity",
    )
    CYCLE_STATES = {
        "INCOMPLETE",
        "ASSESSMENT_RETAINED_NOT_COMMITTED",
        "REVIEW_PENDING",
        "REVIEW_RETAINED_NOT_COMMITTED",
        "REVIEWED_PASS",
        "REVIEWED_BLOCKED",
    }
    ACTIONS = tuple(
        "physical_received_camera_" + name
        for name in (
            "files_discover",
            "draft_start",
            "draft_record",
            "submit",
            "review",
            "export",
        )
    ) + ("physical_camera_identity_begin",)
    CONTEXT_KEYS = _StaticCameraOnboardingDisplay.CONTEXT_KEYS
    MISSING = {record + "_OBSERVATION_REQUIRED" for record in RECORDS} | set(
        "NOTEBOOK_CAMERA_STAGE_ORIGINAL_NOT_BOUND BOARD_THICKNESS_OUTSIDE_ACCOMMODATION STRUCTURED_CAMERA_INSPECTION_REQUIRED INSPECTION_NOTEBOOK_REFERENCE_NOT_BOUND CAMERA_RECEIPT_INSPECTION_UNCERTAIN CAMERA_MANUFACTURER_MISMATCH CAMERA_PRODUCT_ID_MISMATCH CAMERA_LENS_FOCAL_LENGTH_MISMATCH CAMERA_OR_LENS_DAMAGE_OBSERVED CAMERA_IDENTITY_LABEL_NOT_LEGIBLE CAMERA_PURCHASE_RECORD_MISMATCH CAMERA_PACKAGE_CONTENTS_INCOMPLETE".split()
    )
    SUBMIT_FIELDS = (
        "file_only",
        "operator_id",
        *("attachment_" + item for item in RECORDS),
        "inspection_state",
        "inspection_observed_now",
        "observed_manufacturer",
        "observed_product_id",
        "observed_camera_serial",
        "observed_lens_focal_length_mm",
        "body_condition",
        "lens_condition",
        "connector_condition",
        "identity_label_legible",
        "purchase_record_matches",
        "package_contents_complete",
        "inspection_uncertain",
        "purchase_choice",
        "inspection_image_choice",
    )

    @staticmethod
    def need(condition):
        if not condition:
            raise ValueError("received-camera cached projection is inconsistent")

    @classmethod
    def keys(cls, value, keys):
        return cls.exact(value, set(keys.split()) if type(keys) is str else keys)

    @classmethod
    def nullable_sha(cls, value):
        return value is None or cls.digest(value)

    @classmethod
    def context(cls, value):
        return _StaticCameraOnboardingDisplay.context(value)

    @classmethod
    def launch(cls, value):
        return _SourceReassessmentDisplay.launch(value)

    @classmethod
    def actor(cls, value):
        return _SourceReassessmentDisplay.actor(value)

    @classmethod
    def receipt_id(cls, value):
        return (
            type(value) is str
            and re.fullmatch(r"receivedcamera-[0-9a-f]{32}", value) is not None
        )

    @classmethod
    def coverage(cls, value):
        return (
            cls.keys(value, "total observed unknown unrecorded")
            and all(cls.integer(item, 0, 16) for item in value.values())
            and value["total"] == 16
            and sum(value[key] for key in ("observed", "unknown", "unrecorded")) == 16
        )

    @classmethod
    def triple(cls, value):
        return cls.keys(value, "receipt assessment review") and all(
            cls.digest(item) for item in value.values()
        )

    @classmethod
    def binding(cls, value):
        return (
            cls.keys(
                value,
                cls.CONTEXT_KEYS
                | {
                    "receipt_id",
                    "collection_launch_id",
                    "operator_id",
                    "static_contract",
                    "camera_request_event_sha256",
                },
            )
            and cls.context({key: value[key] for key in cls.CONTEXT_KEYS})
            and cls.receipt_id(value["receipt_id"])
            and cls.launch(value["collection_launch_id"])
            and cls.actor(value["operator_id"])
            and cls.triple(value["static_contract"])
            and cls.digest(value["camera_request_event_sha256"])
        )

    @classmethod
    def reference(cls, value):
        return (
            cls.keys(
                value,
                "evidence_id stage package_sha256 manifest_sha256 payload_sha256 payload_bytes",
            )
            and cls.identifier(value["evidence_id"])
            and value["stage"] == "camera_receipt"
            and all(
                cls.digest(value[key])
                for key in ("package_sha256", "manifest_sha256", "payload_sha256")
            )
            and cls.integer(value["payload_bytes"], 1, 2097152)
        )

    @classmethod
    def notebook(cls, n, context, requirements, *, launch=None, original_sha=None):
        keys = (
            set("schema binding revision previous_sha256 rows coverage meaning".split())
            | cls.BASE_FLAGS
        )
        if original_sha is None:
            keys.add("snapshot_sha256")
        cls.need(
            cls.keys(n, keys)
            and n["schema"] == "rocell.physical_intake_notebook.v1"
            and cls.integer(n["revision"], 0, 128)
            and cls.digest(original_sha or n.get("snapshot_sha256"))
            and all(n[key] is False for key in cls.BASE_FLAGS)
            and cls.string(n["meaning"], 512)
        )
        cls.need(
            n["previous_sha256"] is None
            if n["revision"] == 0
            else cls.digest(n["previous_sha256"])
        )
        cls.need(
            cls.keys(
                n["binding"],
                "source_sha256 session_id origin_launch_id launch_session_id prerequisites_sha256",
            )
            and context is not None
            and cls.launch(n["binding"]["launch_session_id"])
            and all(
                n["binding"][key] == context[key]
                for key in (
                    "source_sha256",
                    "session_id",
                    "origin_launch_id",
                    "prerequisites_sha256",
                )
            )
            and (launch is None or n["binding"]["launch_session_id"] == launch)
        )
        cls.need(
            cls.coverage(n["coverage"])
            and type(n["rows"]) is list
            and len(n["rows"]) == 16
        )
        questions = (
            None
            if requirements is None
            else next(
                row
                for row in requirements["stages"]
                if row["stage"] == "camera_receipt"
            )["intake_rows"]
        )
        observed = unknown = 0
        for index, row in enumerate(n["rows"]):
            cls.need(
                cls.keys(
                    row,
                    "record_id assembly measurement unit candidate_or_requirement template_phase template_status template_notes required_observation_fields observation acceptance",
                )
                and row["record_id"] == cls.RECORDS[index]
            )
            cls.need(
                all(
                    row[key] == "" or cls.string(row[key], 4096)
                    for key in (
                        "assembly",
                        "measurement",
                        "unit",
                        "candidate_or_requirement",
                        "template_phase",
                        "template_notes",
                    )
                )
                and row["template_status"]
                in (
                    "NOT_CAPTURED",
                    "NOT_CREATED",
                    "NOT_MEASURED",
                    "NOT_RECORDED",
                    "NOT_TESTED",
                    "OPEN_LIMIT",
                )
            )
            cls.need(
                row["required_observation_fields"]
                == [
                    "observed_value",
                    "instrument_or_method",
                    "observed_at_ns",
                    "operator_id",
                    "evidence_references",
                    "uncertainty_or_limitations",
                ]
            )
            deferred = index == 4
            cls.need(
                cls.same_question(
                    row["acceptance"],
                    dict(
                        status="DEFERRED_LIMIT" if deferred else "NOT_ASSESSED",
                        owner_stage=(
                            "noncontact_acceptance" if deferred else "camera_receipt"
                        ),
                        prerequisites=(
                            ["TARGET_ACCURACY_BUDGET_CLOSED"] if deferred else []
                        ),
                        measurement_required=True,
                    ),
                )
            )
            if questions is not None:
                cls.need(
                    cls.same_question({**row, "observation": None}, questions[index])
                )
            observation = row["observation"]
            if observation is None:
                continue
            cls.need(
                cls.keys(
                    observation,
                    "status observed_value method evidence_note operator_id recorded_at_ns",
                )
                and observation["status"] in ("OBSERVED", "UNKNOWN")
                and all(
                    cls.entry_text(observation[key], maximum)
                    for key, maximum in (
                        ("observed_value", 256),
                        ("method", 512),
                        ("evidence_note", 1024),
                        ("operator_id", 64),
                    )
                )
                and cls.integer(observation["recorded_at_ns"], 1, 2**63 - 1)
            )
            if observation["status"] == "OBSERVED":
                if row["unit"] in ("mm", "g"):
                    cls.need(
                        re.fullmatch(
                            r"[0-9]+(?:\.[0-9]+)?", observation["observed_value"]
                        )
                        is not None
                        and (
                            deferred
                            or re.search(r"[1-9]", observation["observed_value"])
                            is not None
                        )
                    )
                observed += 1
            else:
                unknown += 1
        cls.need(
            n["coverage"]
            == dict(
                total=16,
                observed=observed,
                unknown=unknown,
                unrecorded=16 - observed - unknown,
            )
            and observed + unknown <= n["revision"]
            and (n["revision"] == 0 or observed + unknown > 0)
        )
        cls.need(
            len(
                json.dumps(
                    {key: item for key, item in n.items() if key != "snapshot_sha256"},
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
            )
            <= 65536
        )

    @classmethod
    def foundation(cls, value, submission):
        cls.need(
            cls.keys(
                value,
                set(
                    "schema assessment_sha256 binding notebook_sha256 inspection_sha256 status coverage row_checks thickness flatness_acceptance missing_requirements residuals notebook_original_bound".split()
                )
                | cls.BASE_FLAGS,
            )
        )
        cls.need(
            value["schema"] == "rocell.received_camera_record_assessment_summary.v1"
            and cls.digest(value["assessment_sha256"])
            and all(value[key] is False for key in cls.BASE_FLAGS)
            and type(value["notebook_original_bound"]) is bool
        )
        cls.need(
            all(
                cls.same_question(value[key], submission[key])
                for key in (
                    "binding",
                    "notebook_sha256",
                    "inspection_sha256",
                    "coverage",
                )
            )
        )
        missing = value["missing_requirements"]
        cls.need(
            type(missing) is list
            and len(missing) <= 32
            and len(set(missing)) == len(missing)
            and set(missing) <= cls.MISSING
        )
        cls.need(
            value["status"] == ("RECEIPT_INCOMPLETE" if missing else "RECEIPT_COMPLETE")
            and value["flatness_acceptance"] == "DEFERRED_LIMIT"
        )
        cls.need(
            type(value["residuals"]) is list
            and len(value["residuals"]) == 6
            and all(
                type(item) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", item)
                for item in value["residuals"]
            )
        )
        cls.need(type(value["row_checks"]) is list and len(value["row_checks"]) == 16)
        for index, row in enumerate(value["row_checks"]):
            cls.need(
                cls.keys(row, "record_id observation_status acceptance")
                and row["record_id"] == cls.RECORDS[index]
                and row["observation_status"] in ("OBSERVED", "UNKNOWN", "UNRECORDED")
                and row["acceptance"]
                == (
                    "DEFERRED_LIMIT"
                    if index == 4
                    else (
                        "THICKNESS_ACCOMMODATION"
                        if index in (2, 3)
                        else "RECORDED_NOT_QUALIFIED"
                    )
                )
            )
        thickness = value["thickness"]
        cls.need(
            cls.keys(
                thickness,
                "minimum_mm maximum_mm status allowed_minimum_mm allowed_maximum_mm",
            )
            and thickness["allowed_minimum_mm"] == "17.5"
            and thickness["allowed_maximum_mm"] == "18.5"
            and thickness["status"]
            in ("UNOBSERVED", "WITHIN_ACCOMMODATION", "OUTSIDE_ACCOMMODATION")
            and all(
                thickness[key] is None
                or (
                    cls.entry_text(thickness[key], 256)
                    and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", thickness[key]) is not None
                )
                for key in ("minimum_mm", "maximum_mm")
            )
        )
        cls.need(
            value["status"] != "RECEIPT_COMPLETE"
            or (
                value["coverage"]["observed"] == 16
                and thickness["status"] == "WITHIN_ACCOMMODATION"
                and value["notebook_original_bound"] is True
            )
        )

    @classmethod
    def inspection(cls, value, submission, notebook):
        names = (
            "observed_manufacturer",
            "observed_product_id",
            "observed_camera_serial",
        )
        conditions = ("body_condition", "lens_condition", "connector_condition")
        flags = (
            "identity_label_legible",
            "purchase_record_matches",
            "package_contents_complete",
            "inspection_uncertain",
        )
        cls.need(
            submission is not None
            and notebook is not None
            and cls.keys(
                value,
                set(
                    "schema binding operator_id observed_at_ns observed_lens_focal_length_mm purchase_record_evidence_id inspection_image_evidence_ids authority receipt_sha256".split()
                )
                | set(names + conditions + flags),
            )
        )
        cls.need(
            value["schema"] == "rocell.physical_onboarding.camera_receipt_inspection.v1"
            and value["receipt_sha256"] == submission["inspection_sha256"]
            and value["operator_id"] == submission["binding"]["operator_id"]
            and cls.integer(value["observed_at_ns"], 1, 2**63 - 1)
            and all(
                cls.string(value[key], 2048) and len(value[key]) <= 512 for key in names
            )
            and (
                value["observed_lens_focal_length_mm"] is None
                or cls.integer(value["observed_lens_focal_length_mm"], 1, 500)
            )
            and all(
                value[key] in ("ACCEPTABLE", "DAMAGED", "UNCERTAIN")
                for key in conditions
            )
            and all(type(value[key]) is bool for key in flags)
        )
        cls.need(
            cls.same_question(
                value["authority"],
                dict(
                    scope="DIAGNOSTIC_EVIDENCE_ONLY",
                    hardware_commands_generated=0,
                    power_commands_generated=0,
                    motion_commands_generated=0,
                    contact_commands_generated=0,
                    power_authorized=False,
                    motion_authorized=False,
                    contact_authorized=False,
                    build_promotion_authorized=False,
                    session_mutation_effect="NONE",
                    physical_release_effect="NONE",
                ),
            )
        )
        b = value["binding"]
        cls.need(
            cls.keys(
                b,
                "source_binding_sha256 session_header_sha256 session_id cell_id stage_plan_sha256 stage evidence binding_sha256",
            )
            and all(
                cls.digest(b[key])
                for key in (
                    "source_binding_sha256",
                    "session_header_sha256",
                    "stage_plan_sha256",
                    "binding_sha256",
                )
            )
            and b["session_header_sha256"] == submission["binding"]["header_sha256"]
            and b["session_id"] == submission["binding"]["session_id"]
            and b["cell_id"] == submission["binding"]["cell_id"]
            and b["stage"] == "camera_receipt"
        )
        refs = b["evidence"]
        cls.need(
            type(refs) is list
            and 1 <= len(refs) <= 32
            and all(cls.reference(ref) for ref in refs)
            and len({ref["evidence_id"] for ref in refs}) == len(refs)
            and notebook["reference"] in refs
        )
        ids = {ref["evidence_id"] for ref in refs}
        images = value["inspection_image_evidence_ids"]
        cls.need(
            value["purchase_record_evidence_id"] in ids
            and type(images) is list
            and 1 <= len(images) <= 32
            and len(set(images)) == len(images)
            and set(images) <= ids
        )

    @classmethod
    def roles(cls, value, context, requirements):
        cls.need(
            cls.keys(
                value,
                "receipt_id sequence state notebook inspection submission assessment review",
            )
            and cls.receipt_id(value["receipt_id"])
            and cls.integer(value["sequence"], 1, 4)
            and value["state"] in cls.CYCLE_STATES
        )
        n, s, a, r = (
            value[key] for key in ("notebook", "submission", "assessment", "review")
        )
        if n is not None:
            cls.need(
                cls.keys(n, "document evidence_sha256 reference")
                and cls.digest(n["evidence_sha256"])
                and cls.reference(n["reference"])
                and n["reference"]["payload_sha256"] == n["evidence_sha256"]
                and n["reference"]["payload_bytes"] <= 65536
            )
            cls.notebook(
                n["document"], context, requirements, original_sha=n["evidence_sha256"]
            )
        for item in (s, a, r):
            if item is not None:
                cls.need(
                    cls.binding(item.get("binding"))
                    and all(
                        item["binding"][key] == context[key] for key in cls.CONTEXT_KEYS
                    )
                    and item["binding"]["receipt_id"] == value["receipt_id"]
                    and type(item["sequence"]) is int
                    and item["sequence"] == value["sequence"]
                    and all(item[key] is False for key in cls.ROLE_FLAGS)
                    and len(json.dumps(item, ensure_ascii=True, separators=(",", ":")))
                    <= 24576
                )
        if s is not None:
            cls.need(
                n is not None
                and cls.keys(
                    s,
                    set(
                        "schema submission_sha256 status binding sequence predecessor coverage notebook_sha256 inspection_sha256 draft_origin_notebook_sha256 carried_forward_record_ids attachment_count attachment_bytes linked_row_count".split()
                    )
                    | cls.ROLE_FLAGS,
                )
                and s["schema"] == "rocell.received_camera_submission_summary.v1"
                and s["status"] == "SUBMISSION_COLLECTED"
                and cls.digest(s["submission_sha256"])
                and s["notebook_sha256"] == n["evidence_sha256"]
                and cls.same_question(s["coverage"], n["document"]["coverage"])
                and cls.nullable_sha(s["inspection_sha256"])
                and cls.nullable_sha(s["draft_origin_notebook_sha256"])
            )
            cls.need(
                s["predecessor"] is None
                if s["sequence"] == 1
                else cls.keys(s["predecessor"], "submission assessment review")
                and all(cls.digest(item) for item in s["predecessor"].values())
            )
            cls.need(
                type(s["carried_forward_record_ids"]) is list
                and s["carried_forward_record_ids"]
                == [
                    key for key in cls.RECORDS if key in s["carried_forward_record_ids"]
                ]
                and cls.integer(s["attachment_count"], 0, 16)
                and cls.integer(s["attachment_bytes"], 0, 4194304)
                and cls.integer(s["linked_row_count"], s["coverage"]["observed"], 16)
            )
        if a is not None:
            cls.need(
                s is not None
                and cls.keys(
                    a,
                    set(
                        "schema assessment_sha256 status binding sequence submission_sha256 foundation_sha256 verdict missing_requirements foundation".split()
                    )
                    | cls.ROLE_FLAGS,
                )
                and a["schema"]
                == "rocell.received_camera_submission_assessment_summary.v1"
                and a["status"] == "ASSESSED"
                and cls.digest(a["assessment_sha256"])
                and cls.same_question(a["binding"], s["binding"])
                and a["submission_sha256"] == s["submission_sha256"]
            )
            cls.foundation(a["foundation"], s)
            cls.need(
                a["foundation_sha256"] == a["foundation"]["assessment_sha256"]
                and a["missing_requirements"] == a["foundation"]["missing_requirements"]
                and a["verdict"]
                == (
                    "PASS"
                    if a["foundation"]["status"] == "RECEIPT_COMPLETE"
                    else "BLOCKED"
                )
            )
        if r is not None:
            cls.need(
                a is not None
                and cls.keys(
                    r,
                    set(
                        "schema binding sequence meaning submission_sha256 assessment_sha256 decision verdict reviewer_id review_launch_id reviewed_at_ns distinct_operator_labels review_sha256 status".split()
                    )
                    | cls.ROLE_FLAGS,
                )
                and r["schema"] == "rocell.received_camera_submission_review_summary.v1"
                and r["status"] == "REVIEW_RECORDED"
                and cls.same_question(r["binding"], s["binding"])
                and cls.digest(r["review_sha256"])
                and r["submission_sha256"] == s["submission_sha256"]
                and r["assessment_sha256"] == a["assessment_sha256"]
                and r["decision"] in ("ACKNOWLEDGE_EXACT", "REJECT")
                and r["verdict"]
                == ("BLOCKED" if r["decision"] == "REJECT" else a["verdict"])
                and cls.actor(r["reviewer_id"])
                and r["reviewer_id"].casefold()
                != s["binding"]["operator_id"].casefold()
                and cls.launch(r["review_launch_id"])
                and cls.integer(r["reviewed_at_ns"], 1, 2**63 - 1)
                and r["distinct_operator_labels"] is True
                and cls.string(r["meaning"], 512)
            )
        if value["inspection"] is not None:
            cls.inspection(value["inspection"], s, n)
        cls.need(
            s is None
            or (s["inspection_sha256"] is None) == (value["inspection"] is None)
        )
        cls.need(
            value["state"]
            not in ("ASSESSMENT_RETAINED_NOT_COMMITTED", "REVIEW_PENDING")
            or (a is not None and r is None)
        )
        cls.need(
            value["state"]
            not in (
                "REVIEW_RETAINED_NOT_COMMITTED",
                "REVIEWED_PASS",
                "REVIEWED_BLOCKED",
            )
            or r is not None
        )
        cls.need(
            value["state"] not in ("REVIEWED_PASS", "REVIEWED_BLOCKED")
            or r["verdict"] == value["state"].removeprefix("REVIEWED_")
        )

    @classmethod
    def publication(cls, value):
        return (
            cls.keys(value, "status operation_id")
            and value["status"]
            in ("NOT_PUBLISHED", "PENDING", "CURRENT", "HISTORICAL_HELD")
            and (value["operation_id"] is None or cls.identifier(value["operation_id"]))
        )

    @classmethod
    def inbox(cls, value, source, launch, publication):
        cls.need(cls.keys(value, "discovery choices"))
        d, choices = value["discovery"], value["choices"]
        cls.need(
            cls.keys(
                d,
                "schema status directory source_sha256 launch_session_id discovery_sha256 files issues physical_authority device_io_performed",
            )
            and d["schema"] == "rocell.physical_intake_inbox.v1"
            and d["status"] in ("NOT_DISCOVERED", "READY", "HELD")
            and d["source_sha256"] == source
            and d["launch_session_id"] == launch
            and d["physical_authority"] is False
            and d["device_io_performed"] is False
            and cls.string(d["directory"], 4096)
        )
        path = d["directory"].replace("\\", "/")
        cls.need(
            re.match(r"^(?:[A-Za-z]:/|/)", path) is not None
            and ".." not in path.split("/")
            and path.endswith("/software/runs/physical-intake-inbox")
        )

        def name(item):
            return (
                type(item) is str
                and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,94}", item) is not None
                and not item.endswith(".")
                and re.match(
                    r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", item, re.I
                )
                is None
            )

        mime = dict(
            txt="text/plain",
            json="application/json",
            png="image/png",
            jpg="image/jpeg",
            jpeg="image/jpeg",
            pdf="application/pdf",
        )
        cls.need(type(d["files"]) is list and len(d["files"]) <= 32)
        for item in d["files"]:
            cls.need(
                cls.keys(
                    item, "choice_id basename media_type payload_bytes payload_sha256"
                )
                and type(item["choice_id"]) is str
                and re.fullmatch(r"intake-file-[0-9a-f]{32}", item["choice_id"])
                is not None
                and name(item["basename"])
                and mime.get(item["basename"].split(".")[-1].lower())
                == item["media_type"]
                and cls.integer(item["payload_bytes"], 1, 2097152)
                and cls.digest(item["payload_sha256"])
            )
        cls.need(
            len({item["choice_id"] for item in d["files"]}) == len(d["files"])
            and len({item["basename"] for item in d["files"]}) == len(d["files"])
            and sum(item["payload_bytes"] for item in d["files"]) <= 16777216
        )
        issues = {
            "INTAKE_INBOX_" + key
            for key in "BUSY INVALID LIMIT UNSAFE_FILE FILE_LIMIT FILE_TYPE CONTENT CHANGED STALE_CHOICE SOURCE_CHANGED CANCELLED DEADLINE READ_FAILED".split()
        }
        cls.need(
            type(d["issues"]) is list
            and len(d["issues"]) <= 33
            and all(
                cls.keys(item, "code basename")
                and item["code"] in issues
                and (item["basename"] is None or name(item["basename"]))
                for item in d["issues"]
            )
        )
        cls.need(
            cls.digest(d["discovery_sha256"])
            if d["status"] == "READY"
            else d["discovery_sha256"] is None and not d["files"]
        )
        cls.need(d["status"] != "NOT_DISCOVERED" or not d["issues"])
        cls.need(
            type(choices) is list
            and len(choices) <= 32
            and all(
                cls.keys(item, "value label")
                and any(item["value"] == file["choice_id"] for file in d["files"])
                and cls.string(item["label"], 256)
                for item in choices
            )
            and len({item["value"] for item in choices}) == len(choices)
            and (publication == "CURRENT" or not choices)
        )

    @classmethod
    def export_receipt(cls, value):
        if value is None:
            return
        cls.need(
            cls.keys(
                value,
                "status valid path export_root export_id files total_bytes manifest_sha256 physical_authority provenance limitations",
            )
            and value["status"] == "EXPORTED_DIAGNOSTICS"
            and value["valid"] is True
            and value["physical_authority"] == "NONE"
            and cls.string(value["path"], 16384)
            and cls.string(value["export_root"], 16384)
            and cls.identifier(value["export_id"])
            and cls.digest(value["manifest_sha256"])
            and cls.integer(value["total_bytes"], 1, 16777216)
        )
        p = value["provenance"]
        cls.need(
            cls.keys(
                p,
                "session_id mode source_binding_sha256 source_identity software_version",
            )
            and cls.launch(p["session_id"])
            and p["mode"] == "PHYSICAL_DIAGNOSTIC"
            and cls.digest(p["source_binding_sha256"])
            and cls.keys(p["source_identity"], "source_sha256")
            and p["source_identity"]["source_sha256"] == p["source_binding_sha256"]
            and cls.string(p["software_version"], 128)
        )
        cls.need(
            type(value["limitations"]) is list
            and len(value["limitations"]) <= 16
            and all(cls.string(item, 1024) for item in value["limitations"])
        )
        cls.need(
            type(value["files"]) is list
            and len(value["files"]) <= 11
            and all(
                cls.keys(item, "name bytes sha256")
                and cls.string(item["name"], 128)
                and cls.integer(
                    item["bytes"], 0 if item["name"] == "events.jsonl" else 1, 4194304
                )
                and cls.digest(item["sha256"])
                for item in value["files"]
            )
        )

    @classmethod
    def validate(cls, value, view):
        try:
            return cls._validate(value, view)
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            IndexError,
            StopIteration,
            RecursionError,
            OverflowError,
        ):
            return None

    @classmethod
    def _validate(cls, value, view):
        cls.need(
            type(value) is dict
            and len(
                json.dumps(
                    value, ensure_ascii=True, allow_nan=False, separators=(",", ":")
                )
            )
            <= 384 * 1024
        )
        if value.get("schema") == "rocell.wizard_received_camera_export_pointer.v1":
            cls.need(
                cls.keys(
                    value,
                    "schema source_sha256 launch_session_id original_context publication status latest_subjects draft_sha256 metadata_export separate_metadata_export_required original_received_documents_included private_original_media_included physical_authority hardware_qualified meaning",
                )
                and cls.digest(value["source_sha256"])
                and cls.launch(value["launch_session_id"])
                and cls.publication(value["publication"])
                and (
                    value["original_context"] is None
                    or cls.context(value["original_context"])
                )
                and cls.string(value["status"], 64)
                and cls.nullable_sha(value["draft_sha256"])
                and value["separate_metadata_export_required"] is True
                and all(
                    value[key] is False
                    for key in (
                        "original_received_documents_included",
                        "private_original_media_included",
                        "physical_authority",
                        "hardware_qualified",
                    )
                )
                and cls.string(value["meaning"], 512)
            )
            item = value["latest_subjects"]
            cls.need(
                item is None
                or (
                    cls.keys(
                        item,
                        "receipt_id sequence state notebook_sha256 submission_sha256 assessment_sha256 review_sha256",
                    )
                    and cls.receipt_id(item["receipt_id"])
                    and cls.integer(item["sequence"], 1, 4)
                    and item["state"] in cls.CYCLE_STATES
                    and all(
                        cls.nullable_sha(item[key])
                        for key in (
                            "notebook_sha256",
                            "submission_sha256",
                            "assessment_sha256",
                            "review_sha256",
                        )
                    )
                )
            )
            exported = value["metadata_export"]
            cls.need(
                exported is None
                or (
                    cls.keys(exported, "path export_id manifest_sha256")
                    and cls.string(exported["path"], 16384)
                    and cls.identifier(exported["export_id"])
                    and cls.digest(exported["manifest_sha256"])
                )
            )
            return value
        cls.need(
            cls.keys(
                value,
                set(
                    "schema source_sha256 launch_session_id original_context publication status stage_states draft draft_origin_notebook_sha256 collection inbox identity_entry metadata_export next_action meaning".split()
                )
                | cls.FLAGS,
            )
            and value["schema"] == "rocell.wizard_received_camera.v1"
            and cls.digest(value["source_sha256"])
            and cls.launch(value["launch_session_id"])
            and all(value[key] is False for key in cls.FLAGS)
            and cls.string(value["meaning"], 512)
            and cls.publication(value["publication"])
            and value["status"]
            in (
                "NOT_STARTED",
                "DRAFT",
                "DISCOVERED",
                "REVIEW_PENDING",
                "REVIEWED_PASS",
                "REVIEWED_BLOCKED",
                "INCOMPLETE_HELD",
                "HISTORICAL_HELD",
            )
            and (value["next_action"] is None or value["next_action"] in cls.ACTIONS)
            and cls.nullable_sha(value["identity_entry"])
            and cls.nullable_sha(value["draft_origin_notebook_sha256"])
        )
        c, t, state = (
            value["original_context"],
            value["collection"],
            value["publication"]["status"],
        )
        # Keep the original setup's fifteen-stage validator isolated from this
        # panel's four-stage projection and six collection states.
        setup = _PhysicalSetupDisplay.setup(view.get("physical_camera_setup"))
        requirements = None if setup is None else setup["prerequisites"]
        stages = value["stage_states"]
        cls.need(
            (c is None or cls.context(c))
            and (
                stages is None
                or cls.keys(stages, set(cls.RECEIVED_STAGES))
                and all(
                    item
                    in (
                        "PENDING",
                        "WAITING_OPERATOR",
                        "REVIEW_PENDING",
                        "PASS",
                        "BLOCKED",
                        "INVALIDATED",
                        "INCIDENT_HOLD",
                        "SIDE_EFFECT_UNCERTAIN",
                        "COMPLETE_DIAGNOSTIC",
                    )
                    for item in stages.values()
                )
            )
        )
        cls.inbox(
            value["inbox"], value["source_sha256"], value["launch_session_id"], state
        )
        cls.export_receipt(value["metadata_export"])
        if state == "PENDING":
            cls.need(
                all(
                    value[key] is None
                    for key in (
                        "draft",
                        "collection",
                        "identity_entry",
                        "draft_origin_notebook_sha256",
                        "next_action",
                    )
                )
                and value["inbox"]["discovery"]["status"] == "NOT_DISCOVERED"
                and value["status"] in ("NOT_STARTED", "HISTORICAL_HELD")
            )
            return value
        if value["draft"] is not None:
            cls.notebook(
                value["draft"],
                c,
                requirements,
                launch=value["launch_session_id"] if state == "CURRENT" else None,
            )
        else:
            cls.need(value["draft_origin_notebook_sha256"] is None)
        if t is not None:
            cls.need(c is not None)
            cls.roles(t, c, requirements)
        status = value["status"]
        cls.need(status != "NOT_STARTED" or value["draft"] is None and t is None)
        cls.need(status != "DRAFT" or value["draft"] is not None and state == "CURRENT")
        cls.need(
            status != "DISCOVERED"
            or value["inbox"]["discovery"]["status"] == "READY"
            and t is None
            and value["draft"] is None
        )
        cls.need(
            status not in ("REVIEW_PENDING", "REVIEWED_PASS", "REVIEWED_BLOCKED")
            or t is not None
            and t["state"] == status
            and state == "CURRENT"
        )
        cls.need(
            state != "HISTORICAL_HELD" or status in ("NOT_STARTED", "HISTORICAL_HELD")
        )
        cls.need(state == "CURRENT" or value["next_action"] is None)
        if state == "CURRENT":
            cls.need(
                setup is not None
                and setup["publication"]["status"] == "CURRENT"
                and setup["session"]["verification"] is not None
                and stages is not None
                and value["publication"]["operation_id"] is not None
                and value["source_sha256"]
                == view.get("source_binding_sha256")
                == setup["source_sha256"]
                and value["launch_session_id"]
                == view.get("session_id")
                == setup["launch_session_id"]
                and all(
                    stages[key] == setup["session"]["stages"][i]["state"]
                    for i, key in enumerate(cls.RECEIVED_STAGES)
                )
            )
            bound, verification = (
                setup["session"]["binding"],
                setup["session"]["verification"],
            )
            cls.need(
                requirements is None
                if c is None
                else requirements is not None
                and c["source_sha256"] == value["source_sha256"]
                and c["session_id"] == bound["session_id"]
                and c["cell_id"] == bound["cell_id"]
                and c["origin_launch_id"] == bound["launch_id"]
                and c["header_sha256"] == verification["session"]["header_sha256"]
                and c["prerequisites_sha256"] == requirements["evidence_sha256"]
            )
            cls.need(
                not (t or value["draft"])
                or c is not None
                and stages["workspace_sources"]
                == stages["static_camera_contract"]
                == "PASS"
            )
            cls.need(
                not t
                or t["inspection"] is None
                or t["inspection"]["binding"]["source_binding_sha256"]
                == verification["cell"]["source_binding_sha256"]
            )
            for display, canonical_stage in (
                ("REVIEW_PENDING", "REVIEW_PENDING"),
                ("REVIEWED_PASS", "PASS"),
                ("REVIEWED_BLOCKED", "BLOCKED"),
            ):
                cls.need(
                    status != display or stages["camera_receipt"] == canonical_stage
                )
            cls.need(
                (stages["camera_identity"] == "WAITING_OPERATOR")
                == (value["identity_entry"] is not None)
            )
            if t and t["submission"]:
                design = _StaticCameraOnboardingDisplay.projection(
                    view.get("static_camera_onboarding"), view
                )
                cls.need(
                    design is not None
                    and design["contract"] is not None
                    and design["contract"]["review"] is not None
                    and design["contract"]["review"]["verdict"] == "PASS"
                    and all(
                        t["submission"]["binding"]["static_contract"][role]
                        == design["contract"][role][role + "_sha256"]
                        for role in ("receipt", "assessment", "review")
                    )
                )
        return value


def _noncontact_projection(value: Any) -> dict[str, Any] | None:
    """Validate only cached display data, never recompute or load evidence."""

    def exact(item: Any, keys: str) -> bool:
        return type(item) is dict and set(item) == set(keys.split())

    def digest(item: Any) -> bool:
        return type(item) is str and re.fullmatch(r"[0-9a-f]{64}", item) is not None

    def identifier(item: Any) -> bool:
        return (
            type(item) is str
            and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", item) is not None
        )

    def ids(item: Any, maximum: int = 32) -> bool:
        return (
            type(item) is list
            and len(item) <= maximum
            and all(identifier(row) for row in item)
            and len(set(item)) == len(item)
        )

    def integer(item: Any) -> bool:
        return type(item) is int and abs(item) <= 9_007_199_254_740_991

    def count(item: Any, maximum: int) -> bool:
        return integer(item) and 0 <= item <= maximum

    def short_text(item: Any) -> bool:
        return (
            type(item) is str
            and 0 < len(item.encode("utf-8", errors="replace")) <= 512
            and not re.search(r"[\x00-\x1f\x7f]", item)
        )

    if not (
        exact(
            value,
            "stage evaluation_sha256 selected_inputs_sha256 outcome checks provenance physical_authority meaning safe_summary",
        )
        and value["stage"] == "noncontact_acceptance"
        and value["outcome"] == "BLOCKED"
        and value["physical_authority"] is False
        and digest(value["evaluation_sha256"])
        and digest(value["selected_inputs_sha256"])
        and short_text(value["meaning"])
        and type(value["provenance"]) is dict
        and _compact_check_data(value["provenance"]) is not None
        and type(value["checks"]) is list
        and 1 <= len(value["checks"]) <= 16
    ):
        return None
    for row in value["checks"]:
        if not (
            exact(row, "check_id check_kind passed observed meaning")
            and identifier(row["check_id"])
            and row["check_kind"] in ("NOMINAL", "EXPECTED_FAULT", "INVARIANT")
            and type(row["passed"]) is bool
            and short_text(row["meaning"])
            and _compact_check_data(row["observed"]) is not None
        ):
            return None
    if len({row["check_id"] for row in value["checks"]}) != len(
        value["checks"]
    ) or not any(
        row["check_kind"] == "NOMINAL" and row["passed"] is False
        for row in value["checks"]
    ):
        return None
    s = value["safe_summary"]
    if not (
        exact(
            s,
            "schema nominal_readiness collision_historical static_geometry accuracy selection dependencies not_evaluated physical_authority",
        )
        and s["schema"] == "rocell.rehearsal_noncontact_summary.v1"
        and s["nominal_readiness"] == "BLOCKED"
        and s["physical_authority"] is False
    ):
        return None
    h, g, a, selected, d = (
        s[key]
        for key in (
            "collision_historical",
            "static_geometry",
            "accuracy",
            "selection",
            "dependencies",
        )
    )
    if not (
        exact(
            h,
            "scope status required_body_count proxy_body_count urdf_collision_element_count missing_body_ids unknown_body_ids",
        )
        and h["scope"] == "HISTORICAL_EYE_ON_ARM"
        and h["status"] == "COLLISION_DIAGNOSTIC_BLOCKED_REQUIRED_GEOMETRY_INCOMPLETE"
        and type(h["required_body_count"]) is int
        and h["required_body_count"] == 19
        and count(h["proxy_body_count"], 19)
        and count(h["urdf_collision_element_count"], 100000)
        and ids(h["missing_body_ids"], 19)
        and ids(h["unknown_body_ids"], 19)
        and exact(
            g,
            "status required_body_count required_source_count missing_geometry_body_ids missing_source_keys",
        )
        and g["status"] == "NOT_EVALUATED"
        and type(g["required_body_count"]) is int
        and g["required_body_count"] == 26
        and type(g["required_source_count"]) is int
        and g["required_source_count"] == 9
        and ids(g["missing_geometry_body_ids"], 26)
        and len(g["missing_geometry_body_ids"]) == 26
        and ids(g["missing_source_keys"], 9)
        and exact(
            a,
            "status unit unmeasured_term_ids conservative_error_micrometers remaining_margin_micrometers controls",
        )
        and a["status"] == "BLOCKED_UNBOUNDED"
        and a["unit"] == "micrometers"
        and ids(a["unmeasured_term_ids"], 10)
        and len(a["unmeasured_term_ids"]) == 10
        and a["conservative_error_micrometers"] is None
        and a["remaining_margin_micrometers"] is None
        and type(a["controls"]) is list
        and len(a["controls"]) == 6
    ):
        return None
    for row in a["controls"]:
        if not (
            exact(
                row,
                "case_id disposition blocking_term_ids conservative_error_micrometers eroded_target_radius_micrometers remaining_margin_micrometers",
            )
            and identifier(row["case_id"])
            and ids(row["blocking_term_ids"], 10)
            and integer(row["eroded_target_radius_micrometers"])
        ):
            return None
        if row["disposition"] == "BLOCKED_UNBOUNDED":
            if (
                row["conservative_error_micrometers"] is not None
                or row["remaining_margin_micrometers"] is not None
                or not row["blocking_term_ids"]
            ):
                return None
        elif not (
            row["disposition"]
            in ("BLOCKED_TARGET_MARGIN", "DIAGNOSTIC_FITS_ZERO_AUTHORITY")
            and count(row["conservative_error_micrometers"], 9_007_199_254_740_991)
            and integer(row["remaining_margin_micrometers"])
            and not row["blocking_term_ids"]
            and (
                row["disposition"] != "DIAGNOSTIC_FITS_ZERO_AUTHORITY"
                or (
                    row["eroded_target_radius_micrometers"] > 0
                    and row["remaining_margin_micrometers"] >= 0
                )
            )
        ):
            return None
    if not (
        [row["case_id"] for row in a["controls"]]
        == [
            "real_unmeasured",
            "missing_term",
            "stale_term",
            "domain_term",
            "target_margin",
            "finite_control",
        ]
        and a["controls"][0]["disposition"] == "BLOCKED_UNBOUNDED"
        and len(a["controls"][0]["blocking_term_ids"]) == 10
        and exact(
            selected,
            "domain tool_case_id target_scope keyboard_targets_evaluated keyboard_catalog_total phone_targets_evaluated phone_catalog_total",
        )
        and selected["domain"] == "NOMINAL_SOURCE_GEOMETRY"
        and identifier(selected["tool_case_id"])
        and selected["target_scope"] == "NO_TARGET_REACHABILITY_EVALUATED"
        and all(
            type(selected[key]) is int and selected[key] == expected
            for key, expected in (
                ("keyboard_targets_evaluated", 0),
                ("phone_targets_evaluated", 0),
                ("keyboard_catalog_total", 46),
                ("phone_catalog_total", 29),
            )
        )
        and exact(
            d,
            "reference_binding_sha256 reference_evidence_sha256 predecessor_receipt_sha256 predecessor_assessment_sha256 predecessor_review_sha256 camera_role feedback_role",
        )
        and all(
            digest(d[key])
            for key in (
                "reference_binding_sha256",
                "reference_evidence_sha256",
                "predecessor_receipt_sha256",
                "predecessor_assessment_sha256",
                "predecessor_review_sha256",
            )
        )
        and d["camera_role"] == "DEPENDENCY_ONLY_NOT_NUMERIC_INPUT"
        and d["feedback_role"] == "TRANSPORT_ONLY_NOT_CALIBRATED_JOINT_INPUT"
        and s["not_evaluated"]
        == ["POSE", "ROUTE", "SENSITIVITY", "VISIBILITY", "DYNAMICS", "PHYSICAL_MOTION"]
    ):
        return None
    return value


class _CameraIdentityDisplay(_ReceivedCameraDisplay):
    """Validate cached stage-4 projections without loading or accepting evidence."""

    IDENTITY_FLAGS = {
        "physical_authority",
        "hardware_qualified",
        "native_release_allowed",
        "device_io_performed",
    }
    IDENTITY_ROLE_FLAGS = IDENTITY_FLAGS | {
        "measurement_truth_verified",
        "authenticated_operator_identity",
    }
    IDENTITY_ROLES = ("metadata", "helper", "receipt", "assessment", "review")
    IDENTITY_STATES = {
        "INCOMPLETE",
        "ASSESSMENT_RETAINED_NOT_COMMITTED",
        "REVIEW_PENDING",
        "REVIEW_RETAINED_NOT_COMMITTED",
        "REVIEWED_BLOCKED",
    }
    IDENTITY_STATUSES = {
        "NOT_STARTED",
        "WAITING_METADATA",
        "REVIEW_PENDING",
        "REVIEWED_BLOCKED",
        "INCOMPLETE_HELD",
        "HISTORICAL_HELD",
    }
    MINIMUM_MISSING = {
        "USB_DESCRIPTOR_SERIAL_PROVENANCE_REQUIRED",
        "USB_OPERATING_TOPOLOGY_AND_SPEED_REQUIRED",
        "RECONNECT_AND_REBOOT_IDENTITY_EVIDENCE_REQUIRED",
        "RECEIVED_LABEL_USB_CORRELATION_REQUIRED",
    }
    IDENTITY_MISSING = MINIMUM_MISSING | {
        "ENDPOINT_METADATA_REVIEW_HELD",
        "EXACT_DEVNODE_DRIVER_PROPERTIES_REQUIRED",
        "GENERIC_NATIVE_DRIVER_SERVICE_CORRELATION_REQUIRED",
        "INT018_OBSERVATION_NOT_RECORDED",
    }

    @staticmethod
    def identity_id(value):
        return (
            type(value) is str
            and re.fullmatch(r"cameraidentity-[0-9a-f]{32}", value) is not None
        )

    @staticmethod
    def codes(value, maximum):
        return (
            type(value) is list
            and len(value) <= maximum
            and all(
                type(item) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", item)
                for item in value
            )
            and len(set(value)) == len(value)
        )

    @classmethod
    def identity_export(cls, value, source, *, part_prefix="camera-identity"):
        if value is None:
            return
        cls.need(
            cls.keys(
                value,
                "status valid path export_root export_id files total_bytes manifest_sha256 physical_authority provenance limitations",
            )
        )
        cls.need(
            value["status"] == "EXPORTED_DIAGNOSTICS"
            and value["valid"] is True
            and value["physical_authority"] == "NONE"
            and all(cls.string(value[key], 16384) for key in ("path", "export_root"))
            and cls.identifier(value["export_id"])
            and cls.digest(value["manifest_sha256"])
            and cls.integer(value["total_bytes"], 1, 8388608)
        )
        p = value["provenance"]
        cls.need(
            cls.keys(
                p,
                "session_id mode source_binding_sha256 source_identity software_version",
            )
            and cls.identifier(p["session_id"])
            and p["mode"] == "PHYSICAL_DIAGNOSTIC"
            and p["source_binding_sha256"] == source
            and cls.keys(p["source_identity"], "source_sha256")
            and p["source_identity"]["source_sha256"] == source
            and cls.string(p["software_version"], 64)
            and type(value["limitations"]) is list
            and len(value["limitations"]) <= 16
            and all(cls.string(item, 1024) for item in value["limitations"])
        )
        files = value["files"]
        cls.need(
            type(files) is list
            and 5 <= len(files) <= 12
            and all(
                cls.keys(f, "name bytes sha256")
                and cls.string(f["name"], 128)
                and cls.integer(
                    f["bytes"], 0 if f["name"] == "events.jsonl" else 1, 1048576
                )
                and cls.digest(f["sha256"])
                for f in files
            )
        )
        names = [f["name"] for f in files]
        fixed = {"README.md", "report.json", "events.jsonl", "manifest.json"}
        parts = sorted(set(names) - fixed)
        cls.need(
            len(set(names)) == len(names)
            and fixed <= set(names)
            and parts
            == [
                f"attachment-{part_prefix}-part-{index:02d}.json"
                for index in range(1, len(parts) + 1)
            ]
            and 1 <= len(parts) <= 8
            and sum(f["bytes"] for f in files) == value["total_bytes"]
        )

    @classmethod
    def identity_cycle(cls, cycle, index, count):
        roles = cls.IDENTITY_ROLES
        cls.need(
            cls.keys(cycle, {"identity_id", "sequence", "state", *roles})
            and cls.identity_id(cycle["identity_id"])
            and type(cycle["sequence"]) is int
            and cycle["sequence"] == index + 1
            and cycle["state"] in cls.IDENTITY_STATES
            and (index == count - 1 or cycle["state"] == "REVIEWED_BLOCKED")
        )
        gap = False
        for role in roles:
            r = cycle[role]
            if r is None:
                gap = True
                continue
            extra = (
                {"checks", "missing_requirements"} if role == "assessment" else set()
            )
            cls.need(
                not gap
                and cls.keys(
                    r,
                    {
                        "schema",
                        "sha256",
                        "identity_id",
                        "sequence",
                        "verdict",
                        "meaning",
                    }
                    | cls.IDENTITY_ROLE_FLAGS
                    | extra,
                )
                and r["schema"] == f"rocell.camera_identity_{role}.v1"
                and cls.digest(r["sha256"])
                and r["identity_id"] == cycle["identity_id"]
                and type(r["sequence"]) is int
                and r["sequence"] == cycle["sequence"]
                and r["verdict"]
                == ("BLOCKED" if role in ("assessment", "review") else None)
                and cls.string(r["meaning"], 512)
                and all(r[key] is False for key in cls.IDENTITY_ROLE_FLAGS)
            )
        a = cycle["assessment"]
        if a is not None:
            checks = a["checks"]
            names = {"provider", "service", "version", "inf_path"}
            bools = {
                "received_serial_reported_match",
                "endpoint_selection_available",
                "exact_devnode_driver_observed",
                "generic_driver_service_matches",
            }
            cls.need(
                cls.keys(
                    checks,
                    bools
                    | {
                        "native_review_blockers",
                        "driver_protocol_schema",
                        "driver_field_availability",
                        "operator_observation_state",
                    },
                )
                and all(type(checks[key]) is bool for key in bools)
                and cls.codes(checks["native_review_blockers"], 32)
                and checks["driver_protocol_schema"]
                in (
                    "rocell.windows_camera_identity.v1",
                    "rocell.windows_camera_identity.v2",
                )
                and cls.keys(checks["driver_field_availability"], names)
                and all(
                    item in ("NOT_RETAINED", "OBSERVED", "UNAVAILABLE")
                    for item in checks["driver_field_availability"].values()
                )
                and checks["operator_observation_state"] in ("UNKNOWN", "OBSERVED")
                and cls.codes(a["missing_requirements"], 16)
                and cls.MINIMUM_MISSING
                <= set(a["missing_requirements"])
                <= cls.IDENTITY_MISSING
            )
            availability = checks["driver_field_availability"]
            cls.need(
                checks["exact_devnode_driver_observed"]
                == all(item == "OBSERVED" for item in availability.values())
            )
            if checks["driver_protocol_schema"].endswith(".v1"):
                cls.need(
                    not checks["exact_devnode_driver_observed"]
                    and all(item == "NOT_RETAINED" for item in availability.values())
                )
        if cycle["state"] in ("ASSESSMENT_RETAINED_NOT_COMMITTED", "REVIEW_PENDING"):
            cls.need(a is not None and cycle["review"] is None)
        if cycle["state"] in ("REVIEW_RETAINED_NOT_COMMITTED", "REVIEWED_BLOCKED"):
            cls.need(cycle["review"] is not None)

    @classmethod
    def _validate(cls, value, view):
        cls.need(type(value) is dict)
        pointer = (
            value.get("schema") == "rocell.wizard_camera_identity_export_pointer.v1"
        )
        base = set(
            "schema source_sha256 launch_session_id original_context publication status cycles export_receipt physical_authority meaning".split()
        )
        cls.need(
            cls.keys(
                value,
                base
                | (
                    {"separate_metadata_export_required", "original_documents_included"}
                    if pointer
                    else {"stage_states", "identity_entry", "next_action"}
                    | cls.IDENTITY_FLAGS
                ),
            )
        )
        cls.need(
            cls.digest(value["source_sha256"])
            and cls.launch(value["launch_session_id"])
            and (
                value["original_context"] is None
                or cls.context(value["original_context"])
            )
            and cls.publication(value["publication"])
            and value["status"] in cls.IDENTITY_STATUSES
            and value["physical_authority"] is False
            and cls.string(value["meaning"], 512)
            and type(value["cycles"]) is list
            and len(value["cycles"]) <= 4
        )
        cycles = value["cycles"]
        if pointer:
            cls.need(
                value["separate_metadata_export_required"] is True
                and value["original_documents_included"] is False
            )
            e = value["export_receipt"]
            cls.need(
                e is None
                or (
                    cls.keys(e, "path export_id manifest_sha256")
                    and cls.string(e["path"], 16384)
                    and cls.identifier(e["export_id"])
                    and cls.digest(e["manifest_sha256"])
                )
            )
            for index, c in enumerate(cycles):
                cls.need(
                    cls.keys(
                        c,
                        {
                            "identity_id",
                            "sequence",
                            "state",
                            *(role + "_sha256" for role in cls.IDENTITY_ROLES),
                        },
                    )
                    and cls.identity_id(c["identity_id"])
                    and type(c["sequence"]) is int
                    and c["sequence"] == index + 1
                    and c["state"] in cls.IDENTITY_STATES
                    and all(
                        cls.nullable_sha(c[role + "_sha256"])
                        for role in cls.IDENTITY_ROLES
                    )
                )
            return value
        cls.need(
            value["schema"] == "rocell.wizard_camera_identity_onboarding.v1"
            and len(
                json.dumps(value, ensure_ascii=True, allow_nan=False).encode("ascii")
            )
            <= 131072
            and all(value[key] is False for key in cls.IDENTITY_FLAGS)
            and value["next_action"]
            in (
                None,
                "physical_camera_identity_submit",
                "physical_camera_identity_review",
                "physical_camera_identity_export",
            )
            and cls.nullable_sha(value["identity_entry"])
        )
        s = value["stage_states"]
        stage_names = cls.RECEIVED_STAGES
        cls.need(
            s is None
            or (
                cls.keys(s, set(stage_names))
                and all(item in _PhysicalSetupDisplay.STATES for item in s.values())
            )
        )
        for index, c in enumerate(cycles):
            cls.identity_cycle(c, index, len(cycles))
        cls.need(len({c["identity_id"] for c in cycles}) == len(cycles))
        cls.identity_export(value["export_receipt"], value["source_sha256"])
        publication = value["publication"]["status"]
        if publication == "PENDING":
            cls.need(
                not cycles
                and value["identity_entry"] is None
                and value["next_action"] is None
                and value["status"] in ("NOT_STARTED", "HISTORICAL_HELD")
            )
            return value
        cls.need(publication == "CURRENT" or value["next_action"] is None)
        cls.need(
            publication != "HISTORICAL_HELD"
            or value["status"] in ("HISTORICAL_HELD", "NOT_STARTED")
        )
        if publication == "CURRENT":
            setup = _PhysicalSetupDisplay.setup(view.get("physical_camera_setup"))
            cls.need(
                setup is not None
                and setup["publication"]["status"] == "CURRENT"
                and s is not None
            )
            b = setup["session"]["binding"]
            verification = setup["session"]["verification"]
            c = value["original_context"]
            cls.need(
                verification is not None
                and value["publication"]["operation_id"] is not None
                and value["source_sha256"]
                == view.get("source_binding_sha256")
                == setup["source_sha256"]
                and value["launch_session_id"]
                == view.get("session_id")
                == setup["launch_session_id"]
                and all(
                    s[key] == setup["session"]["stages"][index]["state"]
                    for index, key in enumerate(stage_names)
                )
            )
            if c is None:
                cls.need(setup["prerequisites"] is None)
            else:
                cls.need(
                    setup["prerequisites"] is not None
                    and c["source_sha256"] == value["source_sha256"]
                    and c["session_id"] == b["session_id"]
                    and c["cell_id"] == b["cell_id"]
                    and c["origin_launch_id"] == b["launch_id"]
                    and c["header_sha256"] == verification["session"]["header_sha256"]
                    and c["prerequisites_sha256"]
                    == setup["prerequisites"]["evidence_sha256"]
                )
            if cycles or value["identity_entry"] is not None:
                cls.need(
                    c is not None
                    and value["identity_entry"] is not None
                    and all(s[key] == "PASS" for key in stage_names[:3])
                )
            if value["status"] in ("REVIEW_PENDING", "REVIEWED_BLOCKED"):
                cls.need(
                    cycles
                    and cycles[-1]["state"] == value["status"]
                    and s["camera_identity"]
                    == (
                        "BLOCKED"
                        if value["status"] == "REVIEWED_BLOCKED"
                        else "REVIEW_PENDING"
                    )
                )
            cls.need(
                value["status"] != "WAITING_METADATA"
                or s["camera_identity"] == "WAITING_OPERATOR"
            )
            cls.need(s["camera_identity"] != "PASS")
        return value


class _UsbIdentityDisplay(_CameraIdentityDisplay):
    """Pure cached presentation; never reads files, queries USB or restores grants."""

    USB_FLAGS = {
        "physical_authority",
        "hardware_qualified",
        "camera_capture_authorized",
        "arm_access_authorized",
    }
    USB_STATUSES = {
        "NOT_STARTED",
        "AWAITING_INSPECTION",
        "AWAITING_REVIEW",
        "READY_TO_QUERY",
        "OBSERVED_UNQUALIFIED",
        "HELD",
        "INCOMPLETE_HELD",
        "HISTORICAL_HELD",
    }
    USB_ACTIONS = {
        "physical_usb_identity_inspect",
        "physical_usb_identity_review",
        "physical_usb_identity_collect",
        "physical_usb_identity_export",
    }
    USB_ROLES = ("inspection", "review", "execution", "observation")
    USB_COUNTS = {
        "api_calls",
        "hub_open_attempts",
        "hub_open_successes",
        "ioctl_attempts",
        "ioctl_successes",
        "descriptor_requests",
        "close_attempts",
        "close_successes",
        "peak_open_handles",
        "remaining_open_handles",
        "returned_bytes",
    }

    @staticmethod
    def usb_code(value):
        return (
            type(value) is str
            and re.fullmatch(r"[A-Za-z0-9_:-]{1,128}", value) is not None
        )

    @staticmethod
    def usb_actor(value):
        return (
            type(value) is str
            and 1 <= len(value) <= 64
            and value.strip() == value
            and all(32 <= ord(c) < 127 for c in value)
        )

    @classmethod
    def usb_summaries(cls, data, *, separate_review=False):
        i, r, e, o = (data[key] for key in cls.USB_ROLES)
        if i is not None:
            cls.need(
                cls.keys(
                    i,
                    "evidence_sha256 operator_id collection_launch_id policy_sha256 operation_sha256 runtime_registration_sha256 helper_sha256 files_verified target",
                )
                and all(
                    cls.digest(i[k])
                    for k in (
                        "evidence_sha256",
                        "policy_sha256",
                        "operation_sha256",
                        "runtime_registration_sha256",
                        "helper_sha256",
                    )
                )
                and cls.usb_actor(i["operator_id"])
                and cls.launch(i["collection_launch_id"])
                and type(i["files_verified"]) is int
                and i["files_verified"] == 20
            )
            t = i["target"]
            cls.need(
                cls.keys(
                    t,
                    "selection_sha256 native_identity_sha256 endpoint_sha256 symbolic_link device_instance_id",
                )
                and all(
                    cls.digest(t[k])
                    for k in (
                        "selection_sha256",
                        "native_identity_sha256",
                        "endpoint_sha256",
                    )
                )
                and all(
                    cls.string(t[k], 4096)
                    for k in ("symbolic_link", "device_instance_id")
                )
            )
        if r is not None:
            cls.need(
                i is not None
                and cls.keys(
                    r,
                    "policy_review_sha256 runtime_review_sha256 identity_sha256 reviewer_id review_launch_id",
                )
                and all(
                    cls.digest(r[k])
                    for k in (
                        "policy_review_sha256",
                        "runtime_review_sha256",
                        "identity_sha256",
                    )
                )
                and cls.usb_actor(r["reviewer_id"])
                and r["reviewer_id"].casefold() != i["operator_id"].casefold()
                and cls.launch(r["review_launch_id"])
            )
        if e is not None:
            cls.need(
                (r is not None or separate_review)
                and cls.keys(
                    e,
                    "schema evidence_sha256 preparation_sha256 status provenance released no_attempt counter_coverage actual_counts process_cleanup_confirmed usb_cleanup_confirmed error cleanup_errors physical_authority hardware_qualified retries",
                )
                and e["schema"] == "rocell.owned_usb_identity_run_summary.v1"
                and all(
                    cls.digest(e[k]) for k in ("evidence_sha256", "preparation_sha256")
                )
                and e["status"]
                in {
                    "OBSERVED",
                    "HELD",
                    "FAILED",
                    "CANCELLED",
                    "TIMED_OUT",
                    "CLEANUP_UNCERTAIN",
                }
                and e["provenance"] in {"PHYSICAL_USB_QUERY", "INCAPABLE_USB_QUERY"}
                and all(
                    type(e[k]) is bool
                    for k in (
                        "released",
                        "no_attempt",
                        "process_cleanup_confirmed",
                        "usb_cleanup_confirmed",
                    )
                )
                and (e["error"] is None or cls.usb_code(e["error"]))
                and type(e["cleanup_errors"]) is list
                and len(e["cleanup_errors"]) <= 16
                and all(cls.usb_code(x) for x in e["cleanup_errors"])
                and e["physical_authority"] is False
                and e["hardware_qualified"] is False
                and type(e["retries"]) is int
                and e["retries"] == 0
            )
            c = e["actual_counts"]
            if e["counter_coverage"] == "NOT_REPORTED":
                cls.need(
                    c is None and not e["no_attempt"] and not e["usb_cleanup_confirmed"]
                )
            else:
                cls.need(
                    e["counter_coverage"] in {"NATIVE_RECEIPT", "NO_PROCESS_CREATED"}
                    and cls.keys(c, cls.USB_COUNTS)
                    and all(cls.integer(n, 0, 524288) for n in c.values())
                    and c["hub_open_attempts"] <= 32
                    and c["close_attempts"] <= 32
                    and c["hub_open_successes"] <= c["hub_open_attempts"]
                    and c["close_successes"] <= c["close_attempts"]
                )
                if e["counter_coverage"] == "NO_PROCESS_CREATED":
                    cls.need(
                        e["no_attempt"]
                        and not e["released"]
                        and not any(c.values())
                        and not e["usb_cleanup_confirmed"]
                    )
                else:
                    cls.need(
                        not e["no_attempt"]
                        and e["usb_cleanup_confirmed"]
                        == (
                            c["remaining_open_handles"] == 0
                            and c["hub_open_successes"]
                            == c["close_successes"]
                            == c["close_attempts"]
                        )
                    )
            if e["status"] == "OBSERVED":
                cls.need(
                    e["released"]
                    and e["counter_coverage"] == "NATIVE_RECEIPT"
                    and e["process_cleanup_confirmed"]
                    and e["usb_cleanup_confirmed"]
                    and e["error"] is None
                    and not e["cleanup_errors"]
                )
        if o is not None:
            cls.need(
                e is not None
                and e["counter_coverage"] == "NATIVE_RECEIPT"
                and cls.keys(
                    o,
                    "outcome serial_values vid pid bcd_usb i_serial_number physical_usb_instance_id host_controller_instance_id hub_port ex_speed ex_v2_available operating_at_superspeed operating_at_superspeed_plus",
                )
                and o["outcome"] in {"OBSERVED", "HELD"}
                and type(o["serial_values"]) is list
                and len(o["serial_values"]) <= 4
                and all(
                    cls.string(x, 508) and len(x) <= 127 for x in o["serial_values"]
                )
                and all(
                    o[k] is None
                    or (type(o[k]) is str and re.fullmatch(r"[0-9a-f]{4}", o[k]))
                    for k in ("vid", "pid")
                )
                and (o["bcd_usb"] is None or cls.integer(o["bcd_usb"], 0, 65535))
                and (
                    o["i_serial_number"] is None
                    or cls.integer(o["i_serial_number"], 0, 255)
                )
                and all(
                    o[k] is None or cls.string(o[k], 4096)
                    for k in ("physical_usb_instance_id", "host_controller_instance_id")
                )
                and (o["hub_port"] is None or cls.integer(o["hub_port"], 1, 255))
                and (o["ex_speed"] is None or cls.integer(o["ex_speed"], 0, 3))
                and type(o["ex_v2_available"]) is bool
                and all(
                    o[k] is None or type(o[k]) is bool
                    for k in ("operating_at_superspeed", "operating_at_superspeed_plus")
                )
            )
            if not o["ex_v2_available"]:
                cls.need(
                    o["operating_at_superspeed"] is None
                    and o["operating_at_superspeed_plus"] is None
                )

    @classmethod
    def _validate(cls, value, view):
        cls.need(
            type(value) is dict
            and len(json.dumps(value, ensure_ascii=False, allow_nan=False)) <= 98304
        )
        pointer = value.get("schema") == "rocell.wizard_usb_identity_export_pointer.v1"
        common = set(
            "schema source_sha256 launch_session_id original_context publication status usb_id export_receipt meaning".split()
        )
        cls.need(
            cls.keys(
                value,
                common
                | (
                    {
                        "coverage",
                        "separate_metadata_export_required",
                        "original_documents_included",
                        "physical_authority",
                    }
                    if pointer
                    else {"stage_states", "next_action", *cls.USB_ROLES} | cls.USB_FLAGS
                ),
            )
            and cls.digest(value["source_sha256"])
            and cls.launch(value["launch_session_id"])
            and (
                value["original_context"] is None
                or cls.context(value["original_context"])
            )
            and cls.publication(value["publication"])
            and value["status"] in cls.USB_STATUSES
            and (
                value["usb_id"] is None
                or (
                    type(value["usb_id"]) is str
                    and re.fullmatch(r"usbidentity-[0-9a-f]{32}", value["usb_id"])
                )
            )
            and cls.string(value["meaning"], 512)
        )
        if pointer:
            cls.need(
                value["separate_metadata_export_required"] is True
                and value["original_documents_included"] is False
                and value["physical_authority"] is False
                and cls.keys(value["coverage"], set(cls.USB_ROLES))
            )
            cls.usb_summaries(value["coverage"])
            receipt = value["export_receipt"]
            cls.need(
                receipt is None
                or (
                    cls.keys(receipt, "path export_id manifest_sha256")
                    and cls.string(receipt["path"], 16384)
                    and cls.identifier(receipt["export_id"])
                    and cls.digest(receipt["manifest_sha256"])
                )
            )
            return value
        cls.need(
            value["schema"] == "rocell.wizard_usb_identity.v1"
            and all(value[k] is False for k in cls.USB_FLAGS)
            and (
                value["next_action"] is None or value["next_action"] in cls.USB_ACTIONS
            )
        )
        cls.usb_summaries(value)
        cls.identity_export(
            value["export_receipt"], value["source_sha256"], part_prefix="usb-identity"
        )
        stage_names = (
            "workspace_sources",
            "static_camera_contract",
            "camera_receipt",
            "camera_identity",
        )
        stage_states = {
            "PENDING",
            "WAITING_OPERATOR",
            "REVIEW_PENDING",
            "PASS",
            "BLOCKED",
            "INVALIDATED",
            "INCIDENT_HOLD",
            "SIDE_EFFECT_UNCERTAIN",
            "COMPLETE_DIAGNOSTIC",
        }
        s, publication = value["stage_states"], value["publication"]["status"]
        cls.need(
            s is None
            or (
                cls.keys(s, set(stage_names))
                and all(x in stage_states for x in s.values())
            )
        )
        if publication == "PENDING":
            cls.need(
                all(value[k] is None for k in cls.USB_ROLES)
                and value["next_action"] is None
                and value["status"] in {"NOT_STARTED", "HISTORICAL_HELD"}
            )
            return value
        cls.need(publication == "CURRENT" or value["next_action"] is None)
        cls.need(
            publication != "HISTORICAL_HELD" or value["status"] == "HISTORICAL_HELD"
        )
        if publication == "CURRENT":
            setup = _PhysicalSetupDisplay.setup(view.get("physical_camera_setup"))
            cls.need(
                setup is not None
                and setup["publication"]["status"] == "CURRENT"
                and s is not None
            )
            b, q, c = (
                setup["session"]["binding"],
                setup["session"]["verification"],
                value["original_context"],
            )
            cls.need(
                q is not None
                and value["publication"]["operation_id"] is not None
                and value["source_sha256"]
                == view.get("source_binding_sha256")
                == setup["source_sha256"]
                and value["launch_session_id"]
                == view.get("session_id")
                == setup["launch_session_id"]
                and all(
                    s[k] == setup["session"]["stages"][j]["state"]
                    for j, k in enumerate(stage_names)
                )
            )
            if c is None:
                cls.need(setup["prerequisites"] is None)
            else:
                cls.need(
                    setup["prerequisites"] is not None
                    and c["source_sha256"] == value["source_sha256"]
                    and c["session_id"] == b["session_id"]
                    and c["cell_id"] == b["cell_id"]
                    and c["origin_launch_id"] == b["launch_id"]
                    and c["header_sha256"] == q["session"]["header_sha256"]
                    and c["prerequisites_sha256"]
                    == setup["prerequisites"]["evidence_sha256"]
                )
            i, r, e, o = (value[k] for k in cls.USB_ROLES)
            if any(x is not None for x in (i, r, e, o)):
                cls.need(
                    c is not None
                    and value["usb_id"] is not None
                    and all(s[k] == "PASS" for k in stage_names[:3])
                    and s["camera_identity"] != "PASS"
                )
            if value["status"] == "AWAITING_REVIEW":
                cls.need(i is not None and r is None)
            if value["status"] == "READY_TO_QUERY":
                cls.need(r is not None and e is None)
            if value["status"] == "OBSERVED_UNQUALIFIED":
                cls.need(
                    e is not None
                    and e["status"] == "OBSERVED"
                    and o is not None
                    and o["outcome"] == "OBSERVED"
                )
        return value


class _UsbQualificationDisplay(_UsbIdentityDisplay):
    """Cached original declaration/baseline; rendering never acquires anything."""

    ABSENCE_ACTIONS = {
        "physical_usb_absence_begin",
        "physical_usb_absence_boot_review",
        "physical_usb_absence_boot_collect",
        "physical_usb_absence_runtime_review",
        "physical_usb_absence_collect",
    }
    RECONNECT_ACTIONS = {
        "physical_usb_reconnect_" + name
        for name in ("begin", "prepare", "review", "boot_collect", "collect")
    }

    REBOOT_ACTIONS = {
        "physical_usb_reboot_" + name
        for name in ("begin", "prepare", "review", "boot_collect", "collect")
    }

    @classmethod
    def reconnect(cls, a, outer, *, reboot=False, historical=False):
        # Two exact display contracts share common metadata fields; no proof is relabeled.
        phase_name = "REBOOT" if reboot else "RECONNECT"
        if a is None:
            cls.need(
                outer["status"]
                not in {phase_name + "_ACTIVE", phase_name + "_RETAINED_BLOCKED"}
            )
            return
        stamp = lambda x: type(x) is int and 0 < x < 2**63
        cls.need(
            cls.keys(
                a,
                set(
                    "phase_id state phase_start_event_sha256 phase_started_at_utc_ns operator_event acquisition_ledger preparation target review host_boot execution observation phase_record".split()
                )
                | cls.USB_FLAGS,
            )
            and type(a["phase_id"]) is str
            and re.fullmatch(r"usbphase-[0-9a-f]{32}", a["phase_id"]) is not None
            and a["state"]
            in {
                "PREPARATION_REQUESTED",
                "PREPARED",
                "REVIEWED",
                "BOOT_REQUESTED",
                "BOOT_RETAINED",
                "BOOT_HELD",
                "BOOT_UNCERTAIN",
                "QUERY_REQUESTED",
                "RETAINED_BLOCKED",
                "INCOMPLETE",
                "ORIGINAL_CAMPAIGN_HELD",
            }
            and all(a[k] is False for k in cls.USB_FLAGS)
            and (
                a["phase_start_event_sha256"] is None
                or cls.digest(a["phase_start_event_sha256"])
            )
            and (
                a["phase_started_at_utc_ns"] is None
                or stamp(a["phase_started_at_utc_ns"])
            )
            and outer["plan"] is not None
            and outer["absence"] is not None
            and outer["absence"]["state"] == "RETAINED_BLOCKED"
            and outer["absence"]["phase_record"]["physical_node_absence_observed"]
            is True
        )
        if reboot:
            cls.need(
                outer["reconnect"] is not None
                and outer["reconnect"]["state"] == "RETAINED_BLOCKED"
                and outer["reconnect"]["phase_record"]["status"]
                == "RECONNECT_OBSERVATIONS_RETAINED"
                and a["phase_id"] != outer["reconnect"]["phase_id"]
            )
        report, ledger, prep, target, review, boot, final = (
            a[k]
            for k in (
                "operator_event",
                "acquisition_ledger",
                "preparation",
                "target",
                "review",
                "host_boot",
                "phase_record",
            )
        )
        if report is not None:
            cls.need(
                cls.keys(
                    report,
                    "evidence_sha256 operator_id launch_session_id reported_at_utc_ns event",
                )
                and cls.digest(report["evidence_sha256"])
                and cls.usb_actor(report["operator_id"])
                and cls.launch(report["launch_session_id"])
                and stamp(report["reported_at_utc_ns"])
                and stamp(a["phase_started_at_utc_ns"])
                and report["reported_at_utc_ns"] >= a["phase_started_at_utc_ns"]
                and report["event"]
                == (
                    "OPERATOR_REPORTED_HOST_RESTARTED"
                    if reboot
                    else "OPERATOR_REPORTED_CAMERA_USB_RECONNECTED"
                )
            )
        if ledger is not None:
            cls.need(
                report is not None
                and cls.keys(
                    ledger,
                    "schema source_sha256 session_id launch_session_id trial_id phase_id phase_started_at_utc_ns entries",
                )
                and ledger["schema"]
                == "rocell.usb_phase_metadata_acquisition_ledger.v1"
                and ledger["source_sha256"] == outer["source_sha256"]
                and ledger["session_id"] == outer["original_context"]["session_id"]
                and ledger["launch_session_id"] == report["launch_session_id"]
                and ledger["trial_id"] == outer["plan"]["binding"]["trial_id"]
                and ledger["phase_id"] == a["phase_id"]
                and ledger["phase_started_at_utc_ns"] == a["phase_started_at_utc_ns"]
                and type(ledger["entries"]) is list
                and len(ledger["entries"]) <= 3
            )
            roster = (
                ("GENERIC_INVENTORY", "inventory_devices"),
                ("NATIVE_INVENTORY", "native_camera_inventory"),
                ("NATIVE_IDENTITY", "native_camera_identity"),
            )
            prior, ids = report["reported_at_utc_ns"], {a["phase_id"]}
            for row, (role, action) in zip(ledger["entries"], roster):
                cls.need(
                    cls.keys(
                        row,
                        "role action_id operation_id started_at_utc_ns finished_at_utc_ns published_at_utc_ns document_sha256 result_sha256 completion_logged",
                    )
                    and row["role"] == role
                    and row["action_id"] == action
                    and cls.identifier(row["operation_id"])
                    and row["operation_id"] not in ids
                    and cls.digest(row["document_sha256"])
                    and cls.digest(row["result_sha256"])
                    and row["completion_logged"] is True
                    and all(
                        stamp(row[k])
                        for k in (
                            "started_at_utc_ns",
                            "finished_at_utc_ns",
                            "published_at_utc_ns",
                        )
                    )
                    and prior
                    <= row["started_at_utc_ns"]
                    <= row["finished_at_utc_ns"]
                    <= row["published_at_utc_ns"]
                )
                prior = row["published_at_utc_ns"]
                ids.add(row["operation_id"])
        if prep is not None:
            cls.need(
                report is not None
                and ledger is not None
                and len(ledger["entries"]) == 3
                and cls.keys(
                    prep,
                    "preparation_sha256 operator_id prepared_at_utc_ns enrollment_sha256 operation_sha256 runtime_registration_sha256 file_count",
                )
                and all(
                    cls.digest(prep[k])
                    for k in (
                        "preparation_sha256",
                        "enrollment_sha256",
                        "operation_sha256",
                        "runtime_registration_sha256",
                    )
                )
                and prep["operator_id"] == report["operator_id"]
                and stamp(prep["prepared_at_utc_ns"])
                and prep["prepared_at_utc_ns"]
                >= ledger["entries"][-1]["published_at_utc_ns"]
                and cls.integer(prep["file_count"], 1, 32)
            )
        if target is not None:
            cls.need(
                prep is not None
                and cls.keys(
                    target,
                    "selection_sha256 native_identity_sha256 endpoint_sha256 symbolic_link device_instance_id",
                )
                and all(
                    cls.digest(target[k])
                    for k in (
                        "selection_sha256",
                        "native_identity_sha256",
                        "endpoint_sha256",
                    )
                )
                and all(
                    cls.string(target[k], 4096)
                    for k in ("symbolic_link", "device_instance_id")
                )
            )
        if review is not None:
            cls.need(
                prep is not None
                and target is not None
                and cls.keys(
                    review,
                    "identity_sha256 policy_review_sha256 runtime_review_sha256 operator_id reviewer_id review_launch_id boot_request_sha256",
                )
                and all(
                    cls.digest(review[k])
                    for k in (
                        "identity_sha256",
                        "policy_review_sha256",
                        "runtime_review_sha256",
                        "boot_request_sha256",
                    )
                )
                and review["operator_id"] == prep["operator_id"]
                and cls.usb_actor(review["reviewer_id"])
                and review["reviewer_id"].casefold() != review["operator_id"].casefold()
                and review["review_launch_id"] == report["launch_session_id"]
            )
        if boot is not None:
            cls.need(
                review is not None
                and cls.keys(
                    boot,
                    "schema original_state observation_sha256 status origin host_key_sha256 boot_key_sha256 last_boot_up_time_utc process_status tree_exit_confirmed blockers boot_relation physical_authority hardware_qualified device_io_performed"
                    + (
                        " restart_status reconnect_finished_at_utc_ns phase_started_at_utc_ns"
                        if reboot
                        else ""
                    ),
                )
                and boot["schema"]
                == (
                    "rocell.wizard_usb_reboot_boot_summary.v1"
                    if reboot
                    else "rocell.wizard_usb_reconnect_boot_summary.v1"
                )
                and boot["original_state"]
                in {
                    "BOOT_REQUESTED",
                    "BOOT_RETAINED",
                    "BOOT_HELD",
                    "BOOT_UNCERTAIN",
                    "INCOMPLETE",
                }
                and cls.digest(boot["observation_sha256"])
                and boot["status"] in {"HELD", "OBSERVED_HOST_BOOT"}
                and boot["origin"]
                in {
                    "WINDOWS_LOCAL_CIM",
                    "INJECTED_CIM_EXECUTOR",
                    "INCAPABLE_OWNED_CHILD",
                }
                and all(
                    boot[k] is None or cls.digest(boot[k])
                    for k in ("host_key_sha256", "boot_key_sha256")
                )
                and (
                    boot["last_boot_up_time_utc"] is None
                    or (
                        type(boot["last_boot_up_time_utc"]) is str
                        and re.fullmatch(
                            r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z",
                            boot["last_boot_up_time_utc"],
                        )
                        is not None
                    )
                )
                and boot["process_status"]
                in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}
                and type(boot["tree_exit_confirmed"]) is bool
                and type(boot["blockers"]) is list
                and len(boot["blockers"]) <= 32
                and all(cls.usb_code(code) for code in boot["blockers"])
                and boot["boot_relation"]
                in {"HELD", "SAME_HOST_SAME_BOOT", "SAME_HOST_DIFFERENT_BOOT"}
                and all(
                    boot[k] is False
                    for k in (
                        "physical_authority",
                        "hardware_qualified",
                        "device_io_performed",
                    )
                )
            )
            if reboot:
                cls.need(
                    boot["restart_status"]
                    in {"NOT_EVALUATED", "BOOT_RETAINED", "BOOT_HELD", "BOOT_UNCERTAIN"}
                    and all(
                        boot[k] is None or stamp(boot[k])
                        for k in (
                            "reconnect_finished_at_utc_ns",
                            "phase_started_at_utc_ns",
                        )
                    )
                    and (
                        boot["phase_started_at_utc_ns"] is None
                        or boot["phase_started_at_utc_ns"]
                        == a["phase_started_at_utc_ns"]
                    )
                )
                if boot["original_state"] == "BOOT_RETAINED":
                    cls.need(
                        boot["restart_status"] == "BOOT_RETAINED"
                        and boot["reconnect_finished_at_utc_ns"] is not None
                        and boot["phase_started_at_utc_ns"] is not None
                        and boot["reconnect_finished_at_utc_ns"]
                        < boot["phase_started_at_utc_ns"]
                    )
            if boot["status"] == "OBSERVED_HOST_BOOT":
                cls.need(
                    boot["host_key_sha256"] is not None
                    and boot["boot_key_sha256"] is not None
                    and boot["last_boot_up_time_utc"] is not None
                )
            if boot["original_state"] == "BOOT_RETAINED":
                cls.need(
                    boot["status"] == "OBSERVED_HOST_BOOT"
                    and boot["origin"] == "WINDOWS_LOCAL_CIM"
                    and boot["tree_exit_confirmed"]
                    and boot["process_status"] == "SUCCEEDED"
                    and not boot["blockers"]
                    and boot["boot_relation"]
                    == ("SAME_HOST_DIFFERENT_BOOT" if reboot else "SAME_HOST_SAME_BOOT")
                )
        cls.usb_summaries(
            dict(
                inspection=None,
                review=None,
                execution=a["execution"],
                observation=a["observation"],
            ),
            separate_review=True,
        )
        if a["execution"] is not None:
            cls.need(
                review is not None
                and boot is not None
                and boot["original_state"] == "BOOT_RETAINED"
            )
        if final is not None:
            cls.need(
                a["execution"] is not None
                and cls.keys(
                    final,
                    "phase_sha256 status boot_relation values comparisons checks missing_requirements",
                )
                and cls.digest(final["phase_sha256"])
                and final["boot_relation"] == boot["boot_relation"]
            )
            fields = set(
                "descriptor_serial vid pid endpoint endpoint_instance physical_usb_instance host_controller port_topology driver_provider driver_service driver_version driver_inf generic_driver_service generic_serial generic_vid generic_pid container_id machine_uuid boot_time_utc".split()
            )
            cls.need(cls.keys(final["values"], fields))
            for item in final["values"].values():
                cls.need(
                    cls.keys(item, "status value sha256")
                    and item["status"]
                    in {"NOT_OBSERVED", "VALUE_RETAINED", "VALUE_IN_ORIGINAL"}
                )
                if item["status"] == "NOT_OBSERVED":
                    cls.need(item["value"] is None and item["sha256"] is None)
                else:
                    cls.need(cls.digest(item["sha256"]))
                    cls.need(
                        item["value"] is None
                        if item["status"] == "VALUE_IN_ORIGINAL"
                        else item["value"] is not None
                        and len(
                            json.dumps(
                                item["value"],
                                ensure_ascii=False,
                                separators=(",", ":"),
                                allow_nan=False,
                            ).encode("utf-8")
                        )
                        <= 128
                    )
            names = sorted(fields - {"boot_time_utc"})
            cls.need(
                type(final["comparisons"]) is list
                and len(final["comparisons"]) == len(names)
            )
            hash_keys = ("baseline_sha256", "reconnect_sha256") + (
                ("reboot_sha256",) if reboot else ()
            )
            for row, name in zip(final["comparisons"], names):
                cls.need(
                    cls.keys(row, {"field", "status", *hash_keys})
                    and row["field"] == name
                )
                hashes = [row[k] for k in hash_keys]
                cls.need(
                    all(value is None or cls.digest(value) for value in hashes)
                    and row[hash_keys[-1]] == final["values"][name]["sha256"]
                    and row["status"]
                    == (
                        "NOT_OBSERVED"
                        if None in hashes
                        else "MATCHED" if len(set(hashes)) == 1 else "CHANGED"
                    )
                )
            checks = (
                "HOST_BOOT_PHYSICAL_OWNED_CLEAN "
                + (
                    "SAME_HOST_DIFFERENT_BOOT_AS_RECONNECT REBOOT_EPOCH_AFTER_RECONNECT_BEFORE_BEGIN "
                    if reboot
                    else "SAME_HOST_SAME_BOOT_AS_ABSENCE "
                )
                + "OPERATOR_REPORT_REVIEW_BOOT_QUERY_ORDER PHYSICAL_OBSERVATION_ORIGINS OWNED_RESULT_CURRENT_COMPLETE REVIEWED_NATIVE_SELECTION OWNED_USB_RUN_SUCCEEDED USB_OBSERVATION_COMPLETE PROCESS_CLEANUP_CONFIRMED NATIVE_CLEANUP_CONFIRMED DRIVER_FIELDS_OBSERVED DRIVER_SERVICE_MATCH V2_OPERATING_USB3_OBSERVED RECEIVED_SERIAL_MATCH GENERIC_VID_PID_MATCH EXACT_ABSENCE_PHYSICAL_NODE_RETURNED "
                + (
                    "BASELINE_AND_RECONNECT_IDENTITY_TOPOLOGY_DRIVER_CONTINUITY"
                    if reboot
                    else "BASELINE_IDENTITY_TOPOLOGY_DRIVER_CONTINUITY"
                )
            ).split()
            cls.need(
                type(final["checks"]) is list
                and len(final["checks"]) == len(checks)
                and all(
                    cls.keys(row, "check_id passed")
                    and row["check_id"] == name
                    and type(row["passed"]) is bool
                    for row, name in zip(final["checks"], checks)
                )
            )
            missing = [row["check_id"] for row in final["checks"] if not row["passed"]]
            cls.need(
                final["missing_requirements"] == missing
                and final["status"]
                == ("HELD" if missing else phase_name + "_OBSERVATIONS_RETAINED")
            )
        if a["state"] == "RETAINED_BLOCKED":
            cls.need(final is not None)
        if outer["status"] == phase_name + "_RETAINED_BLOCKED":
            cls.need(a["state"] == "RETAINED_BLOCKED")
        if historical:
            cls.need(
                a["state"] == "RETAINED_BLOCKED"
                and final is not None
                and (reboot or final["status"] == "RECONNECT_OBSERVATIONS_RETAINED")
            )
        if (
            not historical
            and outer["publication"]["status"] == "CURRENT"
            and report is not None
        ):
            cls.need(report["launch_session_id"] == outer["launch_session_id"])

    @classmethod
    def absence(cls, a, outer, *, historical=False):
        if a is None:
            cls.need(
                outer["status"] not in {"ABSENCE_ACTIVE", "ABSENCE_RETAINED_BLOCKED"}
            )
            return
        states = {
            "PREPARATION_REQUESTED",
            "PREPARED",
            "BOOT_REVIEWED",
            "BOOT_REQUESTED",
            "BOOT_RETAINED",
            "BOOT_HELD",
            "BOOT_UNCERTAIN",
            "PRESENCE_REVIEW_REQUESTED",
            "PRESENCE_REVIEW_PREPARED",
            "RUNTIME_REVIEWED",
            "QUERY_REQUESTED",
            "RETAINED_BLOCKED",
            "INCOMPLETE",
            "ORIGINAL_CAMPAIGN_HELD",
        }
        stamp = lambda x: type(x) is int and 0 < x < 2**63
        cls.need(
            cls.keys(
                a,
                set(
                    "phase_id phase state phase_start_event_sha256 phase_started_at_utc_ns target operator_event preparation boot_intent_sha256 boot_review host_boot runtime_review execution observation phase_record".split()
                )
                | cls.USB_FLAGS,
            )
            and type(a["phase_id"]) is str
            and re.fullmatch(r"usbphase-[0-9a-f]{32}", a["phase_id"]) is not None
            and a["phase"] == "RECONNECT_ABSENCE"
            and a["state"] in states
            and all(a[k] is False for k in cls.USB_FLAGS)
            and (
                a["phase_start_event_sha256"] is None
                or cls.digest(a["phase_start_event_sha256"])
            )
            and (
                a["phase_started_at_utc_ns"] is None
                or stamp(a["phase_started_at_utc_ns"])
            )
            and outer["plan"] is not None
            and outer["baseline"] is not None
            and outer["baseline"]["state"] == "RETAINED_BLOCKED"
        )
        t, r, p, br, b, rr, e, o, f = (
            a[k]
            for k in (
                "target",
                "operator_event",
                "preparation",
                "boot_review",
                "host_boot",
                "runtime_review",
                "execution",
                "observation",
                "phase_record",
            )
        )
        if t is not None:
            cls.need(
                cls.keys(
                    t,
                    "physical_usb_instance_id physical_device_id phase_binding_sha256 baseline_sha256 operation_sha256 runtime_registration_sha256 policy_sha256 launch_session_id",
                )
                and cls.string(t["physical_usb_instance_id"], 4096)
                and re.fullmatch(
                    r"USB\\VID_[0-9A-F]{4}&PID_[0-9A-F]{4}(?:&REV_[0-9A-F]{4})?\\[^\\\x00-\x20\x7f-\uffff]+",
                    t["physical_usb_instance_id"],
                    re.IGNORECASE | re.ASCII,
                )
                is not None
                and t["physical_device_id"]
                == t["physical_usb_instance_id"].rsplit("\\", 1)[0]
                and all(
                    cls.digest(t[k])
                    for k in (
                        "phase_binding_sha256",
                        "baseline_sha256",
                        "operation_sha256",
                        "runtime_registration_sha256",
                        "policy_sha256",
                    )
                )
                and cls.launch(t["launch_session_id"])
            )
        if r is not None:
            cls.need(
                t is not None
                and cls.keys(r, "evidence_sha256 operator_id event reported_at_utc_ns")
                and cls.digest(r["evidence_sha256"])
                and cls.usb_actor(r["operator_id"])
                and r["event"] == "OPERATOR_REPORTED_CAMERA_USB_UNPLUGGED"
                and stamp(r["reported_at_utc_ns"])
                and r["reported_at_utc_ns"] >= a["phase_started_at_utc_ns"]
            )
        if p is not None:
            cls.need(
                r is not None
                and cls.keys(
                    p,
                    "schema preparation_sha256 phase_id launch_session_id operator_id prepared_at_utc_ns phase_started_at_utc_ns phase_binding_sha256 operation_sha256 operator_event_sha256 runtime_registration_sha256 file_count status physical_authority hardware_qualified device_io_performed",
                )
                and p["schema"] == "rocell.usb_absence_preparation_summary.v1"
                and cls.digest(p["preparation_sha256"])
                and p["phase_id"] == a["phase_id"]
                and p["launch_session_id"] == t["launch_session_id"]
                and p["operator_id"] == r["operator_id"]
                and p["phase_started_at_utc_ns"] == a["phase_started_at_utc_ns"]
                and stamp(p["prepared_at_utc_ns"])
                and p["prepared_at_utc_ns"] >= r["reported_at_utc_ns"]
                and all(
                    p[k] == t[k]
                    for k in (
                        "phase_binding_sha256",
                        "operation_sha256",
                        "runtime_registration_sha256",
                    )
                )
                and p["operator_event_sha256"] == r["evidence_sha256"]
                and cls.integer(p["file_count"], 1, 32)
                and p["status"] == "FILES_MATCHED"
                and all(
                    p[k] is False
                    for k in (
                        "physical_authority",
                        "hardware_qualified",
                        "device_io_performed",
                    )
                )
            )
        cls.need(
            a["boot_intent_sha256"] is None
            or (p is not None and cls.digest(a["boot_intent_sha256"]))
        )
        if br is not None:
            cls.need(
                a["boot_intent_sha256"] is not None
                and cls.keys(
                    br,
                    "evidence_sha256 operator_id reviewer_id launch_session_id intent_sha256",
                )
                and cls.digest(br["evidence_sha256"])
                and br["operator_id"] == r["operator_id"]
                and cls.usb_actor(br["reviewer_id"])
                and br["reviewer_id"].casefold() != br["operator_id"].casefold()
                and br["launch_session_id"] == t["launch_session_id"]
                and br["intent_sha256"] == a["boot_intent_sha256"]
            )
        if b is not None:
            cls.need(
                br is not None
                and cls.keys(
                    b,
                    "schema original_state observation_sha256 status origin host_key_sha256 boot_key_sha256 last_boot_up_time_utc process_status tree_exit_confirmed blockers boot_relation physical_authority hardware_qualified device_io_performed",
                )
                and b["schema"] == "rocell.wizard_usb_absence_boot_summary.v1"
                and b["original_state"]
                in {
                    "BOOT_REQUESTED",
                    "BOOT_RETAINED",
                    "BOOT_HELD",
                    "BOOT_UNCERTAIN",
                    "INCOMPLETE",
                }
                and cls.digest(b["observation_sha256"])
                and b["status"] in {"HELD", "OBSERVED_HOST_BOOT"}
                and b["origin"]
                in {
                    "WINDOWS_LOCAL_CIM",
                    "INJECTED_CIM_EXECUTOR",
                    "INCAPABLE_OWNED_CHILD",
                }
                and all(
                    b[k] is None or cls.digest(b[k])
                    for k in ("host_key_sha256", "boot_key_sha256")
                )
                and (
                    b["last_boot_up_time_utc"] is None
                    or (
                        type(b["last_boot_up_time_utc"]) is str
                        and re.fullmatch(
                            r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z",
                            b["last_boot_up_time_utc"],
                        )
                        is not None
                    )
                )
                and b["process_status"]
                in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}
                and type(b["tree_exit_confirmed"]) is bool
                and type(b["blockers"]) is list
                and len(b["blockers"]) <= 32
                and all(cls.usb_code(x) for x in b["blockers"])
                and b["boot_relation"]
                in {"HELD", "SAME_HOST_SAME_BOOT", "SAME_HOST_DIFFERENT_BOOT"}
                and all(
                    b[k] is False
                    for k in (
                        "physical_authority",
                        "hardware_qualified",
                        "device_io_performed",
                    )
                )
            )
            if b["status"] == "OBSERVED_HOST_BOOT":
                cls.need(
                    b["host_key_sha256"]
                    and b["boot_key_sha256"]
                    and b["last_boot_up_time_utc"]
                )
            if b["original_state"] == "BOOT_RETAINED":
                cls.need(
                    b["status"] == "OBSERVED_HOST_BOOT"
                    and b["origin"] == "WINDOWS_LOCAL_CIM"
                    and b["tree_exit_confirmed"]
                    and b["process_status"] == "SUCCEEDED"
                    and not b["blockers"]
                    and b["boot_relation"] == "SAME_HOST_SAME_BOOT"
                )
        if rr is not None:
            cls.need(
                b is not None
                and b["original_state"] == "BOOT_RETAINED"
                and cls.keys(
                    rr,
                    "evidence_sha256 operator_id reviewer_id launch_session_id operation_sha256 helper_sha256 usb_presence_policy_sha256",
                )
                and cls.digest(rr["evidence_sha256"])
                and cls.digest(rr["helper_sha256"])
                and rr["operator_id"] == r["operator_id"]
                and cls.usb_actor(rr["reviewer_id"])
                and rr["reviewer_id"].casefold() != rr["operator_id"].casefold()
                and rr["launch_session_id"] == t["launch_session_id"]
                and rr["operation_sha256"] == t["operation_sha256"]
                and rr["usb_presence_policy_sha256"] == t["policy_sha256"]
            )
        if e is not None:
            cls.need(
                rr is not None
                and cls.keys(
                    e,
                    "schema evidence_sha256 preparation_sha256 provenance status current_complete native_outcome actual_counts no_attempt released process_cleanup_confirmed native_cleanup_confirmed counter_coverage error cleanup_errors physical_authority hardware_qualified retries",
                )
                and e["schema"] == "rocell.owned_usb_presence_run_summary.v1"
                and cls.digest(e["evidence_sha256"])
                and cls.digest(e["preparation_sha256"])
                and e["provenance"]
                in {"PHYSICAL_USB_PRESENCE", "INCAPABLE_USB_PRESENCE"}
                and e["status"]
                in {
                    "PRESENT",
                    "ABSENT",
                    "HELD",
                    "FAILED",
                    "CANCELLED",
                    "TIMED_OUT",
                    "CLEANUP_UNCERTAIN",
                }
                and all(
                    type(e[k]) is bool
                    for k in (
                        "current_complete",
                        "no_attempt",
                        "released",
                        "process_cleanup_confirmed",
                        "native_cleanup_confirmed",
                    )
                )
                and e["current_complete"]
                == (e["status"] in {"PRESENT", "ABSENT", "HELD"})
                and (
                    e["native_outcome"] is None
                    or e["native_outcome"] in {"PRESENT", "ABSENT", "HELD"}
                )
                and (e["error"] is None or cls.usb_code(e["error"]))
                and type(e["cleanup_errors"]) is list
                and len(e["cleanup_errors"]) <= 16
                and all(cls.usb_code(x) for x in e["cleanup_errors"])
                and e["physical_authority"] is False
                and e["hardware_qualified"] is False
                and type(e["retries"]) is int
                and e["retries"] == 0
            )
            c = e["actual_counts"]
            if e["counter_coverage"] == "NOT_REPORTED":
                cls.need(
                    c is None
                    and not e["no_attempt"]
                    and not e["native_cleanup_confirmed"]
                )
            elif e["counter_coverage"] in {"NATIVE_RECEIPT", "NO_PROCESS_CREATED"}:
                cls.need(
                    cls.keys(
                        c, "api_calls device_handle_opens configuration_writes frames"
                    )
                    and cls.integer(c["api_calls"], 0, 4)
                    and all(
                        type(c[k]) is int and c[k] == 0
                        for k in (
                            "device_handle_opens",
                            "configuration_writes",
                            "frames",
                        )
                    )
                )
                cls.need(
                    (
                        e["no_attempt"]
                        and not e["released"]
                        and c["api_calls"] == 0
                        and not e["native_cleanup_confirmed"]
                    )
                    if e["counter_coverage"] == "NO_PROCESS_CREATED"
                    else not e["no_attempt"]
                )
            else:
                cls.need(False)
        if o is not None:
            cls.need(
                e is not None
                and cls.keys(
                    o,
                    "schema observation_sha256 request_sha256 provider target_instance_id outcome error api_calls physical_authority meaning",
                )
                and o["schema"] == "rocell.usb_presence_summary.v1"
                and cls.digest(o["observation_sha256"])
                and cls.digest(o["request_sha256"])
                and o["provider"]
                in {"WINDOWS_CONFIGURATION_MANAGER", "INCAPABLE_FIXTURE"}
                and o["target_instance_id"] == t["physical_usb_instance_id"]
                and o["outcome"] == e["native_outcome"]
                and (o["error"] is None or cls.usb_code(o["error"]))
                and cls.integer(o["api_calls"], 0, 4)
                and e["actual_counts"] is not None
                and o["api_calls"] == e["actual_counts"]["api_calls"]
                and o["physical_authority"] is False
                and cls.string(o["meaning"], 512)
            )
        if e is not None:
            cls.need((e["native_outcome"] is not None) == (o is not None))
        checks = [
            "HOST_BOOT_PHYSICAL_OWNED_CLEAN",
            "SAME_HOST_SAME_BOOT_AS_BASELINE",
            "OPERATOR_REPORT_BOOT_REVIEW_QUERY_ORDER",
            "PRESENCE_OBSERVATION_PHYSICAL_ORIGIN",
            "PRESENCE_OWNED_RESULT_COMPLETE",
            "PRESENCE_PROCESS_CLEANUP_CONFIRMED",
            "PRESENCE_NATIVE_CLEANUP_CONFIRMED",
            "EXACT_PHYSICAL_NODE_ABSENT",
        ]
        if f is not None:
            cls.need(
                e is not None
                and cls.keys(
                    f,
                    "phase_sha256 status presence_outcome boot_relation checks missing_requirements physical_node_absence_observed",
                )
                and cls.digest(f["phase_sha256"])
                and f["presence_outcome"] == e["native_outcome"]
                and f["boot_relation"] == b["boot_relation"]
                and type(f["checks"]) is list
                and len(f["checks"]) == len(checks)
                and all(
                    cls.keys(c, "check_id passed")
                    and c["check_id"] == key
                    and type(c["passed"]) is bool
                    for c, key in zip(f["checks"], checks)
                )
            )
            missing = [c["check_id"] for c in f["checks"] if not c["passed"]]
            cls.need(
                f["missing_requirements"] == missing
                and f["status"]
                == ("HELD" if missing else "ABSENCE_OBSERVATIONS_RETAINED")
                and type(f["physical_node_absence_observed"]) is bool
                and f["physical_node_absence_observed"] == (not missing)
            )
        cls.need(a["state"] != "RETAINED_BLOCKED" or f is not None)
        cls.need(
            outer["status"] != "ABSENCE_RETAINED_BLOCKED"
            or a["state"] == "RETAINED_BLOCKED"
        )
        if historical:
            cls.need(
                a["state"] == "RETAINED_BLOCKED"
                and f is not None
                and f["physical_node_absence_observed"] is True
            )
        if (
            not historical
            and outer["publication"]["status"] == "CURRENT"
            and outer["status"] != "HISTORICAL_HELD"
            and t is not None
        ):
            cls.need(t["launch_session_id"] == outer["launch_session_id"])

    @classmethod
    def baseline(cls, b, outer):
        if b is None:
            cls.need(
                outer["status"] not in {"BASELINE_ACTIVE", "BASELINE_RETAINED_BLOCKED"}
            )
            return
        cls.need(
            cls.keys(
                b,
                set(
                    "phase_id state phase_start_event_sha256 phase_started_at_utc_ns acquisition_ledger preparation target review host_boot execution observation phase_record".split()
                )
                | cls.USB_FLAGS,
            )
        )
        states = {
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
        stamp = lambda x: type(x) is int and 0 < x < 2**63
        cls.need(
            type(b["phase_id"]) is str
            and re.fullmatch(r"usbphase-[0-9a-f]{32}", b["phase_id"]) is not None
            and b["state"] in states
            and all(b[k] is False for k in cls.USB_FLAGS)
            and (
                b["phase_start_event_sha256"] is None
                or cls.digest(b["phase_start_event_sha256"])
            )
            and (
                b["phase_started_at_utc_ns"] is None
                or stamp(b["phase_started_at_utc_ns"])
            )
            and outer["plan"] is not None
        )
        ledger, p, target, review, boot, phase = (
            b[k]
            for k in (
                "acquisition_ledger",
                "preparation",
                "target",
                "review",
                "host_boot",
                "phase_record",
            )
        )
        if ledger is not None:
            cls.need(
                cls.keys(
                    ledger,
                    "schema source_sha256 session_id launch_session_id trial_id phase_id phase_started_at_utc_ns entries",
                )
                and ledger["schema"]
                == "rocell.usb_phase_metadata_acquisition_ledger.v1"
                and ledger["source_sha256"] == outer["source_sha256"]
                and ledger["session_id"] == outer["original_context"]["session_id"]
                and ledger["trial_id"] == outer["plan"]["binding"]["trial_id"]
                and ledger["phase_id"] == b["phase_id"]
                and cls.identifier(ledger["launch_session_id"])
                and ledger["phase_started_at_utc_ns"] == b["phase_started_at_utc_ns"]
                and type(ledger["entries"]) is list
                and len(ledger["entries"]) <= 3
            )
            roster = (
                ("GENERIC_INVENTORY", "inventory_devices"),
                ("NATIVE_INVENTORY", "native_camera_inventory"),
                ("NATIVE_IDENTITY", "native_camera_identity"),
            )
            previous, ids = ledger["phase_started_at_utc_ns"], set()
            for row, (role, action) in zip(ledger["entries"], roster):
                cls.need(
                    cls.keys(
                        row,
                        "role action_id operation_id started_at_utc_ns finished_at_utc_ns published_at_utc_ns document_sha256 result_sha256 completion_logged",
                    )
                    and row["role"] == role
                    and row["action_id"] == action
                    and cls.identifier(row["operation_id"])
                    and row["operation_id"] not in ids
                    and cls.digest(row["document_sha256"])
                    and cls.digest(row["result_sha256"])
                    and row["completion_logged"] is True
                    and all(
                        stamp(row[k])
                        for k in (
                            "started_at_utc_ns",
                            "finished_at_utc_ns",
                            "published_at_utc_ns",
                        )
                    )
                    and previous
                    <= row["started_at_utc_ns"]
                    <= row["finished_at_utc_ns"]
                    <= row["published_at_utc_ns"]
                )
                previous = row["published_at_utc_ns"]
                ids.add(row["operation_id"])
        if p is not None:
            cls.need(
                cls.keys(
                    p,
                    set(
                        "schema phase_id plan_sha256 preparation_sha256 enrollment_sha256 operation_sha256 operator_id phase_started_at_utc_ns prepared_at_utc_ns acquisition_count meaning stage_pass".split()
                    )
                    | cls.USB_FLAGS,
                )
                and p["schema"] == "rocell.usb_trial_baseline_preparation_summary.v1"
                and p["phase_id"] == b["phase_id"]
                and p["plan_sha256"] == outer["plan"]["plan_sha256"]
                and all(
                    cls.digest(p[k])
                    for k in (
                        "preparation_sha256",
                        "enrollment_sha256",
                        "operation_sha256",
                    )
                )
                and cls.usb_actor(p["operator_id"])
                and type(p["acquisition_count"]) is int
                and p["acquisition_count"] == 3
                and cls.string(p["meaning"], 128)
                and p["stage_pass"] is False
                and all(p[k] is False for k in cls.USB_FLAGS)
                and ledger is not None
                and len(ledger["entries"]) == 3
                and p["phase_started_at_utc_ns"] == b["phase_started_at_utc_ns"]
                and stamp(p["prepared_at_utc_ns"])
                and p["prepared_at_utc_ns"]
                >= ledger["entries"][2]["published_at_utc_ns"]
            )
        if target is not None:
            cls.need(
                p is not None
                and cls.keys(
                    target,
                    "selection_sha256 native_identity_sha256 endpoint_sha256 symbolic_link device_instance_id",
                )
                and all(
                    cls.digest(target[k])
                    for k in (
                        "selection_sha256",
                        "native_identity_sha256",
                        "endpoint_sha256",
                    )
                )
                and all(
                    cls.string(target[k], 4096)
                    for k in ("symbolic_link", "device_instance_id")
                )
            )
        if review is not None:
            cls.need(
                p is not None
                and target is not None
                and cls.keys(
                    review,
                    "identity_sha256 policy_review_sha256 runtime_review_sha256 operator_id reviewer_id review_launch_id boot_request_sha256",
                )
                and all(
                    cls.digest(review[k])
                    for k in (
                        "identity_sha256",
                        "policy_review_sha256",
                        "runtime_review_sha256",
                        "boot_request_sha256",
                    )
                )
                and review["operator_id"] == p["operator_id"]
                and cls.usb_actor(review["reviewer_id"])
                and review["reviewer_id"].casefold() != review["operator_id"].casefold()
                and review["review_launch_id"] == ledger["launch_session_id"]
            )
        if boot is not None:
            cls.need(
                review is not None
                and cls.keys(
                    boot,
                    "schema original_state observation_sha256 status origin host_key_sha256 boot_key_sha256 last_boot_up_time_utc process_status tree_exit_confirmed blockers physical_authority hardware_qualified device_io_performed",
                )
                and boot["schema"] == "rocell.wizard_usb_trial_boot_summary.v1"
                and boot["original_state"]
                in {
                    "BOOT_REQUESTED",
                    "BOOT_RETAINED",
                    "BOOT_HELD",
                    "BOOT_UNCERTAIN",
                    "QUERY_REQUESTED",
                    "ORIGINAL_CAMPAIGN_HELD",
                    "RETAINED_BLOCKED",
                    "INCOMPLETE",
                }
                and cls.digest(boot["observation_sha256"])
                and boot["status"] in {"HELD", "OBSERVED_HOST_BOOT"}
                and boot["origin"]
                in {
                    "WINDOWS_LOCAL_CIM",
                    "INJECTED_CIM_EXECUTOR",
                    "INCAPABLE_OWNED_CHILD",
                }
                and all(
                    boot[k] is None or cls.digest(boot[k])
                    for k in ("host_key_sha256", "boot_key_sha256")
                )
                and (
                    boot["last_boot_up_time_utc"] is None
                    or (
                        type(boot["last_boot_up_time_utc"]) is str
                        and re.fullmatch(
                            r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z",
                            boot["last_boot_up_time_utc"],
                        )
                        is not None
                    )
                )
                and boot["process_status"]
                in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}
                and type(boot["tree_exit_confirmed"]) is bool
                and type(boot["blockers"]) is list
                and len(boot["blockers"]) <= 32
                and all(cls.usb_code(x) for x in boot["blockers"])
                and all(
                    boot[k] is False
                    for k in (
                        "physical_authority",
                        "hardware_qualified",
                        "device_io_performed",
                    )
                )
            )
            if boot["status"] == "OBSERVED_HOST_BOOT":
                cls.need(
                    boot["host_key_sha256"]
                    and boot["boot_key_sha256"]
                    and boot["last_boot_up_time_utc"]
                    and boot["tree_exit_confirmed"]
                    and boot["process_status"] == "SUCCEEDED"
                    and not boot["blockers"]
                )
        cls.usb_summaries(
            dict(
                inspection=None,
                review=None,
                execution=b["execution"],
                observation=b["observation"],
            ),
            separate_review=True,
        )
        if b["execution"] is not None:
            cls.need(
                review is not None
                and boot is not None
                and boot["status"] == "OBSERVED_HOST_BOOT"
            )
        if phase is not None:
            roster = (
                "HOST_BOOT_OBSERVED",
                "REVIEWED_NATIVE_SELECTION",
                "OWNED_USB_RUN_SUCCEEDED",
                "USB_OBSERVATION_COMPLETE",
                "PROCESS_CLEANUP_CONFIRMED",
                "NATIVE_CLEANUP_CONFIRMED",
                "DRIVER_FIELDS_OBSERVED",
                "DRIVER_SERVICE_MATCH",
                "V2_OPERATING_USB3_OBSERVED",
            )
            cls.need(
                b["execution"] is not None
                and cls.keys(phase, "phase_sha256 checks provenance")
                and cls.digest(phase["phase_sha256"])
                and type(phase["checks"]) is list
                and len(phase["checks"]) == 9
                and all(
                    cls.keys(row, "check_id passed")
                    and row["check_id"] == key
                    and type(row["passed"]) is bool
                    for row, key in zip(phase["checks"], roster)
                )
            )
            provenance = phase["provenance"]
            cls.need(
                cls.keys(provenance, "usb metadata boot metadata_helper_sha256")
                and provenance["usb"] in {"PHYSICAL_USB_QUERY", "INCAPABLE_USB_QUERY"}
                and provenance["metadata"]
                in {"WINDOWS_NATIVE_METADATA", "INCAPABLE_FIXTURE"}
                and provenance["boot"] == boot["origin"]
                and cls.digest(provenance["metadata_helper_sha256"])
            )
        cls.need(b["state"] != "RETAINED_BLOCKED" or phase is not None)
        cls.need(
            outer["status"] != "BASELINE_RETAINED_BLOCKED"
            or b["state"] == "RETAINED_BLOCKED"
        )
        if (
            outer["publication"]["status"] == "CURRENT"
            and outer["status"] != "HISTORICAL_HELD"
            and p is not None
            and b["state"] != "RETAINED_BLOCKED"
        ):
            cls.need(ledger["launch_session_id"] == outer["launch_session_id"])

    @classmethod
    def _validate(cls, value, view):
        from rocell.application.physical_usb_complete_projection import (
            complete_projection_valid,
        )
        from rocell.application.physical_camera_usb_complete_constants import (
            USB_COMPLETE_STATES,
        )

        version6 = (
            type(value) is dict
            and value.get("schema") == "rocell.wizard_usb_qualification.v6"
        )
        version5 = version6 or (
            type(value) is dict
            and value.get("schema") == "rocell.wizard_usb_qualification.v5"
        )
        version4 = version5 or (
            type(value) is dict
            and value.get("schema") == "rocell.wizard_usb_qualification.v4"
        )
        version3 = type(value) is dict and value.get("schema") in {
            "rocell.wizard_usb_qualification.v3",
            "rocell.wizard_usb_qualification.v4",
            "rocell.wizard_usb_qualification.v5",
            "rocell.wizard_usb_qualification.v6",
        }
        version2 = (
            value.get("schema")
            in {
                "rocell.wizard_usb_qualification.v2",
                "rocell.wizard_usb_qualification.v3",
                "rocell.wizard_usb_qualification.v4",
                "rocell.wizard_usb_qualification.v5",
                "rocell.wizard_usb_qualification.v6",
            }
            if type(value) is dict
            else False
        )
        cls.need(
            cls.keys(
                value,
                set(
                    "schema source_sha256 launch_session_id original_context publication status plan next_action export_receipt meaning".split()
                )
                | set(cls.USB_FLAGS)
                | ({"baseline"} if version2 else set())
                | ({"absence"} if version3 else set())
                | ({"reconnect"} if version4 else set())
                | ({"reboot"} if version5 else set())
                | ({"complete"} if version6 else set()),
            )
        )
        cls.need(
            (version2 or value["schema"] == "rocell.wizard_usb_qualification.v1")
            and cls.digest(value["source_sha256"])
            and cls.launch(value["launch_session_id"])
            and (
                value["original_context"] is None
                or cls.context(value["original_context"])
            )
            and cls.publication(value["publication"])
            and value["status"]
            in (
                {"NOT_DECLARED", "DECLARED", "INCOMPLETE_HELD", "HISTORICAL_HELD"}
                | (
                    {"COMPLETE_REVIEW_READY", *USB_COMPLETE_STATES}
                    if version6
                    else set()
                )
                | (
                    {"REBOOT_READY", "REBOOT_ACTIVE", "REBOOT_RETAINED_BLOCKED"}
                    if version5
                    else set()
                )
                | (
                    {"RECONNECT_ACTIVE", "RECONNECT_RETAINED_BLOCKED"}
                    if version4
                    else set()
                )
                | (
                    {"ABSENCE_ACTIVE", "ABSENCE_RETAINED_BLOCKED"}
                    if version3
                    else set()
                )
                | (
                    {"BASELINE_ACTIVE", "BASELINE_RETAINED_BLOCKED"}
                    if version2
                    else set()
                )
            )
            and value["next_action"]
            in (
                {None, "physical_usb_qualification_declare"}
                | (
                    {"physical_usb_complete_assess", "physical_usb_complete_review"}
                    if version6
                    else set()
                )
                | (cls.RECONNECT_ACTIONS if version4 else set())
                | (cls.REBOOT_ACTIONS if version5 else set())
                | ({"physical_camera_refresh"} if version4 else set())
                | (cls.ABSENCE_ACTIONS if version3 else set())
                | (
                    {
                        "physical_usb_qualification_begin",
                        "physical_usb_qualification_prepare",
                        "physical_usb_qualification_review",
                        "physical_usb_qualification_collect",
                        "physical_usb_identity_export",
                    }
                    if version2
                    else set()
                )
            )
            and all(value[k] is False for k in cls.USB_FLAGS)
            and cls.string(value["meaning"], 1024 if version3 else 512)
            and len(json.dumps(value, ensure_ascii=False, allow_nan=False))
            <= (131072 if version4 else 65536)
        )
        cls.identity_export(
            value["export_receipt"], value["source_sha256"], part_prefix="usb-identity"
        )
        plan, context = value["plan"], value["original_context"]

        def label(text, maximum):
            return (
                cls.string(text, maximum)
                and text == text.strip()
                and all(ord(c) >= 32 and ord(c) != 127 for c in text)
            )

        if plan is not None:
            cls.need(
                cls.keys(
                    plan,
                    "plan_sha256 binding operator_id launch_session_id cable_label port_label received_label phases",
                )
            )
            cls.need(
                cls.digest(plan["plan_sha256"])
                and cls.usb_actor(plan["operator_id"])
                and cls.launch(plan["launch_session_id"])
                and label(plan["cable_label"], 128)
                and label(plan["port_label"], 128)
            )
            binding = plan["binding"]
            hashes = "source_sha256 header_sha256 prerequisites_sha256 identity_entry_sha256 stage_policy_sha256 stage_catalog_sha256 stage_order_sha256".split()
            cls.need(
                cls.keys(
                    binding,
                    set(hashes)
                    | {"trial_id", "cell_id", "session_id", "origin_launch_id"},
                )
                and type(binding["trial_id"]) is str
                and re.fullmatch(r"usbtrial-[0-9a-f]{32}", binding["trial_id"])
                is not None
                and all(cls.digest(binding[k]) for k in hashes)
                and cls.identifier(binding["cell_id"])
                and cls.identifier(binding["session_id"])
                and cls.launch(binding["origin_launch_id"])
            )
            received = plan["received_label"]
            cls.need(
                cls.keys(received, "manufacturer product_id serial inspection_sha256")
                and cls.digest(received["inspection_sha256"])
                and all(
                    label(received[k], 256)
                    for k in ("manufacturer", "product_id", "serial")
                )
                and plan["phases"]
                == ["BASELINE", "RECONNECT_ABSENCE", "AFTER_RECONNECT", "AFTER_REBOOT"]
                and type(plan["phases"]) is list
                and context is not None
                and all(binding[k] == context[k] for k in context)
            )
        publication = value["publication"]["status"]
        if version2:
            cls.baseline(value["baseline"], value)
        if version3:
            cls.absence(value["absence"], value, historical=version5)
        if version4:
            cls.reconnect(value["reconnect"], value, historical=version5)
        if version5:
            cls.reconnect(value["reboot"], value, reboot=True, historical=version6)
            if publication != "PENDING":
                cls.need(
                    plan is not None
                    and value["reconnect"] is not None
                    and value["reconnect"]["phase_record"]["status"]
                    == "RECONNECT_OBSERVATIONS_RETAINED"
                )
        if version6:
            cls.need(complete_projection_valid(value))
        if value["next_action"] == "physical_camera_refresh":
            reconnect = value["reboot"] if version5 else value["reconnect"]
            cls.need(
                version4
                and publication == "HISTORICAL_HELD"
                and reconnect is not None
                and reconnect["state"] == "PREPARATION_REQUESTED"
                and reconnect["operator_event"] is not None
                and reconnect["operator_event"]["launch_session_id"]
                == value["launch_session_id"]
                == view["session_id"]
                and value["source_sha256"] == view["source_binding_sha256"]
                and reconnect["preparation"] is None
                and reconnect["acquisition_ledger"] is not None
                and len(reconnect["acquisition_ledger"]["entries"]) == 3
            )
        if publication == "PENDING":
            cls.need(
                plan is None
                and value["next_action"] is None
                and value["status"] == "NOT_DECLARED"
                and (not version2 or value["baseline"] is None)
                and (not version3 or value["absence"] is None)
                and (not version4 or value["reconnect"] is None)
                and (not version5 or value["reboot"] is None)
                and (not version6 or value["complete"] is None)
            )
            return value
        if publication != "CURRENT":
            cls.need(
                value["next_action"] is None
                or (
                    version4
                    and publication == "HISTORICAL_HELD"
                    and value["next_action"]
                    in {"physical_usb_identity_export", "physical_camera_refresh"}
                )
            )
        if publication == "HISTORICAL_HELD":
            cls.need(value["status"] == "HISTORICAL_HELD")
        cls.need(
            (value["status"] != "DECLARED" or plan is not None)
            and (value["status"] != "NOT_DECLARED" or plan is None)
            and (
                version2
                or value["next_action"] is None
                or value["status"] == "NOT_DECLARED"
            )
        )
        if publication == "CURRENT":
            setup = _PhysicalSetupDisplay.setup(view.get("physical_camera_setup"))
            cls.need(
                setup is not None
                and setup["publication"]["status"] == "CURRENT"
                and value["publication"]["operation_id"] is not None
                and value["source_sha256"]
                == view["source_binding_sha256"]
                == setup["source_sha256"]
                and value["launch_session_id"]
                == view["session_id"]
                == setup["launch_session_id"]
            )
            binding, verified = (
                setup["session"]["binding"],
                setup["session"]["verification"],
            )
            cls.need(verified is not None)
            if version6:
                cls.need(complete_projection_valid(value, setup["session"]["stages"]))
            if context is None:
                cls.need(setup["prerequisites"] is None)
            else:
                cls.need(
                    setup["prerequisites"] is not None
                    and context["source_sha256"] == value["source_sha256"]
                    and context["session_id"] == binding["session_id"]
                    and context["cell_id"] == binding["cell_id"]
                    and context["origin_launch_id"] == binding["launch_id"]
                    and context["header_sha256"] == verified["session"]["header_sha256"]
                    and context["prerequisites_sha256"]
                    == setup["prerequisites"]["evidence_sha256"]
                )
            if plan is not None:
                cls.need(
                    all(
                        row["state"] == "PASS" for row in setup["session"]["stages"][:3]
                    )
                    and (
                        value["status"] != "DECLARED"
                        or setup["session"]["stages"][3]["state"] == "REVIEW_PENDING"
                    )
                )
        return value


class _TerminalWizard:
    def __init__(
        self,
        service: WizardService,
        read_line: Callable[[str], str],
        write_line: Callable[[str], Any],
        sleep: Callable[[float], Any],
    ) -> None:
        self.service = service
        self.read_line = read_line
        self.write_line = write_line
        self.sleep = sleep

    def write(self, value: Any) -> None:
        self.write_line(_display(value))

    def ask(self, prompt: str) -> str:
        answer = self.read_line(_display(prompt))
        if not isinstance(answer, str):
            raise ValueError("Terminal input must be text.")
        if len(answer) > 4096:
            raise ValueError("Terminal input exceeds its 4096-character limit.")
        return answer

    def snapshot(self) -> dict[str, Any]:
        view = self.service.view()
        if not isinstance(view, dict) or type(view.get("revision")) is not int:
            raise ValueError("The service did not return a versioned snapshot.")
        actions = view.get("actions")
        if not isinstance(actions, list):
            raise ValueError("The service did not return an action catalog.")
        seen: set[str] = set()
        for action in actions:
            if not isinstance(action, dict):
                raise ValueError("The action catalog contains an invalid record.")
            identifier = action.get("action_id")
            if (
                not isinstance(identifier, str)
                or not _IDENTIFIER.fullmatch(identifier)
                or identifier in seen
            ):
                raise ValueError(
                    "The action catalog contains an invalid or duplicate ID."
                )
            if type(action.get("enabled")) is not bool:
                raise ValueError(
                    "The action catalog has no explicit eligibility result."
                )
            seen.add(identifier)
        return view

    def show(self, view: dict[str, Any]) -> list[dict[str, Any]]:
        self.write("\nRoCell connection workbench — terminal")
        self.write(
            f"Mode: {view.get('mode', 'NOT_RECORDED')} | Cell: {view.get('cell_id', 'NOT_RECORDED')} | Revision: {view['revision']}"
        )
        self.write(
            f"Session: {view.get('session_id', 'NOT_RECORDED')} | Status: {view.get('status', 'NOT_RECORDED')}"
        )
        self.write(
            {
                "authority": view.get("authority", "No physical authority"),
                "source": view.get(
                    "source",
                    view.get(
                        "source_status",
                        view.get(
                            "source_binding_sha256", view.get("build", "Not recorded")
                        ),
                    ),
                ),
            }
        )
        self.write(
            "Status reads do not open a device. Rehearsals do not verify received hardware."
        )
        self.show_device_metadata(view.get("device_selection"), "CAMERA")
        self.show_camera_helper_registration(view.get("camera_helper_registration"))
        self.show_native_camera_enrollment(
            view.get("native_camera_enrollment"), view.get("device_selection")
        )
        self.show_physical_camera(
            view.get("physical_camera"), launch=view.get("session_id")
        )
        self.show_physical_camera_setup(view.get("physical_camera_setup"))
        self.show_camera_operating_proposal(view.get("camera_operating_proposal"), view)
        self.show_camera_operating_submission(view.get("camera_operating_submission"), view)
        self.show_camera_mode_entry(
            view.get("camera_mode_entry"), view.get("physical_camera_setup")
        )
        self.show_source_reassessment(view.get("source_reassessment"), view)
        self.show_static_camera_onboarding(view.get("static_camera_onboarding"), view)
        self.show_received_camera(view.get("received_camera_onboarding"), view)
        self.show_camera_identity(view.get("camera_identity_onboarding"), view)
        self.show_usb_identity(view.get("usb_identity"), view)
        self.show_usb_qualification(view.get("usb_qualification"), view)
        self.show_physical_intake(
            view.get("physical_intake"), view.get("physical_camera_setup")
        )
        self.show_physical_intake_evidence(view.get("physical_intake_evidence"), view)
        self.show_device_metadata(view.get("device_selection"), "SERIAL")
        readiness = view.get("arm_readiness")
        if (
            isinstance(readiness, dict)
            and readiness.get("schema") == "rocell.arm_wizard_readiness.v1"
            and readiness.get("connected") is False
            and readiness.get("physical_authority") is False
        ):
            self.write("Arm onboarding: next step")
            self.write(readiness)
        self.show_native_arm_metadata(view.get("native_arm_metadata"), view)
        passive = view.get("passive_arm_rehearsal")
        history = view.get("passive_arm_history")
        if (
            isinstance(history, dict)
            and history.get("schema") == "rocell.passive_arm_history_view.v1"
            and history.get("historical_only") is True
            and history.get("physical_authority") is False
            and history.get("connected") is False
            and history.get("replay_allowed") is False
        ):
            self.write("Saved passive arm attempt — historical diagnostics only")
            self.write(history)
        if (
            isinstance(passive, dict)
            and passive.get("schema") == "rocell.wizard_passive_arm_rehearsal_view.v1"
            and passive.get("provenance")
            == "REHEARSAL_ONLY_NOT_RECEIVED_DEVICE_EVIDENCE"
            and passive.get("physical_authority") is False
            and passive.get("connected") is False
        ):
            self.write("Retained passive USB rehearsal — not a hardware connection")
            self.write(passive)
        if view.get("next_step"):
            self.write({"next_step": view["next_step"]})
        rehearsal = view.get("commissioning_rehearsal")
        if isinstance(rehearsal, dict):
            self.write(
                {
                    "separate_rehearsal": {
                        key: rehearsal.get(key)
                        for key in (
                            "status",
                            "session_origin",
                            "directory",
                            "cell_id",
                            "session_id",
                            "stage",
                            "stage_state",
                            "assessment",
                            "next_step",
                            "physical_authority",
                        )
                    }
                }
            )
            self.show_reopening(rehearsal)
            if rehearsal.get("camera_process") is not None:
                self.show_camera_process(rehearsal["camera_process"])
            if rehearsal.get("camera_fault_diagnostic") is not None:
                self.show_camera_fault(rehearsal["camera_fault_diagnostic"])
            if rehearsal.get("camera_configuration") is not None:
                self.show_camera_configuration(rehearsal["camera_configuration"])
            optics = rehearsal.get("optics_evaluation")
            if isinstance(optics, dict):
                self.write(
                    "Retained synthetic optics checks; no installed calibration or replay."
                )
                self.write(
                    {
                        key: optics.get(key)
                        for key in (
                            "stage",
                            "outcome",
                            "evaluation_sha256",
                            "selected_inputs_sha256",
                            "meaning",
                        )
                    }
                )
                checks = optics.get("checks")
                if isinstance(checks, list):
                    self.write({"retained_checks": checks[:16]})
                self.write(
                    "The stage-6 dataset is a dependency only, not the evaluated pixels. Physical authority remains false."
                )
            if rehearsal.get("arm_identity_evaluation") is not None:
                self.show_retained_arm_checks(
                    rehearsal["arm_identity_evaluation"],
                    "Retained synthetic arm-identity checks",
                    ("arm_identity",),
                    "Physical arm identity and firmware are unverified. Injected metadata and a synthetic chassis label are not USB/serial enumeration, a received-unit inspection, or an arm connection.",
                )
            if rehearsal.get("power_evaluation") is not None:
                self.show_retained_arm_checks(
                    rehearsal["power_evaluation"],
                    "Retained synthetic power/startup checks",
                    ("power_safety", "power_on_observation"),
                    "Physical actuator energy, power-off state, startup motion and firmware are unverified. This report is not a power-state observation. No power-on, power-off, reset or firmware control is provided here.",
                )
            if rehearsal.get("arm_feedback_evaluation") is not None:
                self.show_retained_feedback(rehearsal["arm_feedback_evaluation"])
            if rehearsal.get("arm_feedback_process") is not None:
                self.show_arm_process(rehearsal["arm_feedback_process"])
            if rehearsal.get("reference_evaluation") is not None:
                self.show_retained_reference(rehearsal["reference_evaluation"])
            if rehearsal.get("noncontact_evaluation") is not None:
                self.show_retained_noncontact(rehearsal["noncontact_evaluation"])
        if view.get("blockers"):
            self.write({"current_holds": view["blockers"]})
        if view.get("operations"):
            self.write({"operation_status": view["operations"]})
        exports = view.get("exports")
        if isinstance(exports, dict) and exports.get("directory"):
            self.write(f"Assigned export folder: {exports['directory']}")
        available = [action for action in view["actions"] if action["enabled"]]
        self.write("\nAvailable actions:")
        for index, action in enumerate(available, 1):
            self.write(
                f"  {index}. {action.get('label', action['action_id'])} [{action['action_id']}]"
            )
        if not available:
            self.write(
                "  None; resolve the current holds without changing authority flags."
            )
        held = [action for action in view["actions"] if not action["enabled"]]
        if held:
            self.write("Held actions:")
            for action in held:
                self.write(
                    {
                        "action": action.get("label", action["action_id"]),
                        "reasons": action.get("blocked_reasons", ["Not eligible"]),
                    }
                )
        self.write(
            "Commands: action number or listed ID, view, export, quit. :back cancels field entry."
        )
        return available

    def show_device_metadata(self, data: Any, kind: str) -> None:
        self.write(
            "Camera metadata candidate review"
            if kind == "CAMERA"
            else "Arm serial metadata candidate review"
        )
        self.write(
            "Read-only inventory snapshot — not a current connection or received-model verification."
        )
        self.write(
            {
                "connection": "NOT_CONNECTED",
                "qualification": "NOT_QUALIFIED",
                "physical_authority": False,
            }
        )
        self.write(
            "Received model: UNKNOWN. A display name, USB VID/PID, unit serial or metadata acknowledgment cannot qualify the camera or arm. No persistent device binding is created."
        )
        selected = _device_metadata(data)
        if selected is None:
            self.write(
                "No metadata inventory snapshot is available. Run an eligible explicit inventory action; no candidate is selected."
                if data is None
                else "NOT_VERIFIED: Device metadata is inconsistent or exceeds display bounds. Inspect diagnostics; no candidate or review is inferred."
            )
        else:
            origin = selected["provenance"]
            self.write(
                {
                    "snapshot_status": selected["status"],
                    "mode": origin["mode"],
                    "scope": origin["scope"],
                    "report_sha256": selected["report_sha256"] or "NOT_RECORDED",
                    "operation_id": selected["operation_id"] or "NOT_RECORDED",
                    "source_sha256": origin["source_sha256"],
                    "platform_system": origin["platform_system"] or "NOT_RECORDED",
                    "captured_timestamp": (
                        "NOT_RECORDED"
                        if origin["captured_at_unix_ns"] is None
                        else "RETAINED_NOT_INTERPRETED"
                    ),
                }
            )
            if selected["invalidation_reason"]:
                self.write(selected["invalidation_reason"])
            if selected["status"] == "INVALIDATED":
                self.write(
                    "This metadata snapshot was invalidated. No prior review is current; obtain a new explicit snapshot before reviewing a candidate."
                )
            else:
                device = selected["devices"][kind]
                if not device["candidates"]:
                    self.write(
                        "No candidates in this snapshot. This is not evidence that the device is absent or disconnected now."
                    )
                for candidate in device["candidates"]:
                    self.write(
                        f"{candidate['display_name']} — {len(candidate['identity_blockers'])} identity blockers"
                    )
                    self.write(
                        {
                            key: (
                                candidate[key]
                                if candidate[key] is not None
                                else "NOT_RECORDED"
                            )
                            for key in (
                                "choice_id",
                                "candidate_sha256",
                                "display_name",
                                "vid",
                                "pid",
                                "unit_serial",
                                "source",
                            )
                        }
                    )
                    if candidate["identity_blockers"]:
                        self.write(
                            {"identity_blockers": candidate["identity_blockers"]}
                        )
                    else:
                        self.write(
                            "No identity blocker was recorded in this snapshot. Received identity, connection and qualification remain unverified."
                        )
                if device["review"] is None:
                    self.write(
                        "No metadata review recorded for this device. Nothing is automatically selected."
                    )
                else:
                    self.write("Explicit metadata acknowledgment — not a connection")
                    self.write(device["review"])
        self.write(
            "Opening or refreshing this view does not discover, select, preview, connect or open a device. Use the separate inventory and review actions with an explicit choice and metadata-only acknowledgment. This review cannot authorize capture, serial access, power changes, motion or contact."
        )

    def show_native_arm_metadata(self, data: Any, view: dict[str, Any]) -> None:
        self.write("Native arm metadata correlation")
        self.write("NOT_CONNECTED / NOT_QUALIFIED")
        self.write(
            "Received arm model, firmware, boot behavior and actuator-power isolation remain unverified. Metadata correlation does not create a ReviewedControllerBinding, persistent open permission or motion authority."
        )
        selected = _native_arm_metadata(data, view)
        if selected is None:
            self.write(
                "No native arm metadata report is available. Review a SERIAL candidate, then use an eligible explicit metadata action."
                if data is None
                else "NATIVE_ARM_METADATA_NOT_VERIFIED: Inconsistent or unbounded cached report withheld. Inspect diagnostics; no current correlation is inferred."
            )
        else:
            self.write(f"Publication: {selected['status']}")
            if selected["invalidation_reason"]:
                self.write(selected["invalidation_reason"])
            if selected["status"] == "HISTORICAL_HELD":
                self.write(
                    "Historical metadata only. Original source, launch and candidate remain attached; these observations are not the current reviewed device. No automatic reinspection, reconnect or identity-to-open authorization."
                )
            report = selected["report"]
            if report is None:
                self.write(
                    "No retained native report. No device absence, identity or driver state is inferred."
                )
            else:
                self.write(f"Correlation result: {report['status']}")
                self.write(
                    "INCAPABLE REHEARSAL: Injected metadata only; no host device was observed."
                    if report["binding"]["mode"] == "rehearsal"
                    else "WINDOWS METADATA OBSERVATION ONLY: A retained observation is not proof of the currently connected unit or an atomically bound open handle."
                )
                self.write(report["binding"])
                self.write(report["provenance"])
                self.write(
                    {key: report[key] for key in ("report_sha256", "snapshot_sha256")}
                )
                self.write("Collection and matching counts")
                self.write(report["counts"])
                self.write("Native field availability — values are not exposed")
                for field, status in report["native_fields"].items():
                    self.write(f"{field}: {status}")
                if report["blockers"]:
                    self.write({"correlation_holds": report["blockers"]})
                else:
                    self.write(
                        "Exactly one generic/native metadata match was retained. This is not connection, driver qualification, received-model verification or permission to open a port."
                    )
        self.write(
            "Unit serial is generic inventory metadata, not a native USB-descriptor observation. Export original diagnostics to the assigned folder. Viewing never enumerates metadata, selects a port, prepares an action or sends serial bytes."
        )

    def show_camera_helper_registration(self, data: Any) -> None:
        self.write("Camera metadata helper inspection & review")
        self.write(
            "One fixed catalogued helper; separate file inspection and exact-report review."
        )
        self.write(
            {
                "camera_connection": "NOT_CONNECTED",
                "camera_qualification": "NOT_QUALIFIED",
                "physical_authority": False,
            }
        )
        self.write(
            "Metadata registration permits only eligible inventory and identity lookups after separate explicit actions. It does not permit probe or capture; separate purpose-specific runtime gates apply. It does not qualify a camera unit, driver, process containment or a trusted release."
        )
        selected = _camera_helper_registration(data)
        if selected is None:
            self.write(
                "No helper inspection snapshot is available. Inspect the fixed catalog through an eligible explicit action; no helper is registered by viewing this page."
                if data is None
                else "NOT_VERIFIED: Helper registration metadata is inconsistent, stale or exceeds display bounds. Inspect diagnostics; no helper registration is inferred."
            )
        else:
            origin = selected["provenance"]
            self.write(
                {
                    "status": selected["status"],
                    "mode": origin["mode"],
                    "scope": origin["scope"],
                    "source_sha256": origin["source_sha256"],
                    "metadata_operations": "inventory, identity",
                    "probe_allowed": False,
                    "capture_allowed": False,
                    "physical_authority": False,
                }
            )
            if origin["mode"] == "rehearsal":
                self.write(
                    "INCAPABLE FIXTURE: rehearsal inspection is synthetic and does not describe installed helper files or register a physical provider."
                )
            if selected["invalidation_reason"]:
                self.write("Latest inspection/review reset or hold")
                self.write(selected["invalidation_reason"])
            if selected["inspection"]:
                self.write("Retained fixed-catalog inspection")
                self.write(selected["inspection"])
                if not selected["inspection"]["eligible_for_metadata_registration"]:
                    self.write(
                        "This inspection cannot register the metadata helper. Missing, changed, unsafe or unreadable files remain held; acknowledgment does not repair or install them."
                    )
            else:
                self.write(
                    "No inspection retained. Default physical startup is unregistered. Visiting this page does not discover or hash helper files."
                )
            if selected["review"]:
                self.write(
                    "Helper review remains held"
                    if selected["status"] == "REVIEW_HELD"
                    else "Exact helper report reviewed for metadata only"
                )
                self.write(selected["review"])
                self.write(
                    "Distinct operator/reviewer labels are diagnostic audit labels, not proof of authenticated independent people."
                )
            else:
                self.write(
                    "No helper review recorded. A distinct reviewer label and metadata-only consent are required; no review or consent is automatic."
                )
            if selected["status"] == "INVALIDATED":
                self.write(
                    "Inspection and review are no longer current. No prior registration is restored or operation replayed."
                )
            if selected["blockers"]:
                self.write("Remaining helper and physical-qualification holds")
                self.write(selected["blockers"])
        self.write(
            "Matching catalogued files does not establish current full-build provenance, trusted-release status, runtime process containment or driver qualification. No unprojected qualification flag is inferred."
        )
        self.write(
            "This card performs no discovery, file hashing, helper installation or process launch. Use explicit inspect and review actions; any later native metadata lookup requires its own preview, consent and execution. No source activation, probe, capture, power, motion or contact authority is granted."
        )

    def show_native_camera_enrollment(self, data: Any, generic: Any) -> None:
        self.write("Native camera endpoint enrollment")
        self.write(
            "Metadata-only inventory, exact endpoint identity and explicit review. No camera activation."
        )
        self.write(
            {
                "connection": "NOT_CONNECTED",
                "qualification": "NOT_QUALIFIED",
                "physical_authority": False,
            }
        )
        self.write(
            "No persistent-unit binding or physical authority. Exact endpoint mapping is not proof of received camera model, USB3 topology/link speed, camera readiness or permission to capture. Names never establish identity."
        )
        selected = _native_camera_enrollment(data, generic)
        if selected is None:
            self.write(
                "No native endpoint enrollment snapshot is available. Inspect the eligible actions and helper registration holds; no native endpoint is selected."
                if data is None
                else "NOT_VERIFIED: Native enrollment metadata is inconsistent, stale or exceeds display bounds. Inspect diagnostics; no endpoint review or binding is inferred."
            )
        else:
            origin = selected["provenance"]
            self.write(
                {
                    "snapshot_status": selected["status"],
                    "mode": origin["mode"],
                    "scope": origin["scope"],
                    "provider_provenance": origin["provider_provenance"]
                    or "NOT_REGISTERED",
                    "helper_sha256": origin["helper_sha256"] or "NOT_REGISTERED",
                    "source_sha256": origin["source_sha256"],
                    "inventory_sha256": selected["inventory_sha256"] or "NOT_RECORDED",
                    "inventory_operation_id": selected["inventory_operation_id"]
                    or "NOT_RECORDED",
                    "generic_candidate_sha256": selected["generic_candidate_sha256"]
                    or "NOT_RECORDED",
                    "generic_report_sha256": selected["generic_report_sha256"]
                    or "NOT_RECORDED",
                    "generic_operation_id": selected["generic_operation_id"]
                    or "NOT_RECORDED",
                }
            )
            if selected["status"] == "PROVIDER_UNAVAILABLE":
                self.write(
                    "Native metadata helper registration is required. No provider is registered; this view does not search for, install or execute a helper."
                )
            if selected["invalidation_reason"]:
                self.write("Latest reset or hold")
                self.write(selected["invalidation_reason"])
            if selected["status"] == "INVALIDATED":
                self.write(
                    "The native enrollment was invalidated. Old endpoint choices, identity and review are not current; no operation is replayed."
                )
            if not selected["candidates"]:
                self.write(
                    "No native endpoint choices retained. This is not a live absence check."
                )
            for candidate in selected["candidates"]:
                self.write(candidate)
            self.write(
                "Identical names remain distinct opaque choices. Compare the exact endpoint hashes and identity evidence; no first-device or same-name fallback is used. Duplicate endpoint identity may remain ambiguous."
            )
            if selected["identity"]:
                self.write("Retained endpoint identity metadata")
                self.write(selected["identity"])
                self.write(
                    "Mapping observed, generic-device match and container match are separate metadata results. False may mean unavailable or inconsistent evidence; it is not a received-model or connectivity verdict."
                )
            else:
                self.write(
                    "No endpoint identity retained. Run an eligible explicit identity action; browsing never performs the lookup."
                )
            if selected["review"]:
                self.write(
                    "Explicit native review remains held"
                    if selected["status"] == "REVIEW_HELD"
                    else "Explicit native endpoint metadata review"
                )
                self.write(
                    {
                        **selected["review"],
                        "binding_meaning": "DIAGNOSTIC_METADATA_ONLY_NOT_PERSISTENT_UNIT_BINDING",
                    }
                )
            else:
                self.write(
                    "No native review recorded. Nothing is automatically selected or acknowledged."
                )
            if selected["blockers"]:
                self.write("Remaining enrollment and qualification holds")
                self.write(selected["blockers"])
        self.write(
            "This card performs no inventory, identity lookup, review, helper call or camera activation. Use the separate actions with explicit metadata-only consent, preview and execution. These operations do not grant capture, calibration, power, motion or contact authority."
        )

    def show_intake_question(self, row: dict[str, Any]) -> None:
        self.write(f"Selected intake question {row['record_id']}: {row['measurement']}")
        self.write(
            {
                "assembly": row["assembly"],
                "source_unit": row["unit"] or "No unit specified",
                "candidate_or_requirement_NOT_OBSERVED": row[
                    "candidate_or_requirement"
                ],
                "source_notes": row["template_notes"],
            }
        )
        self.write(
            "INT-005 flatness: a draft value does not accept a flatness limit. Acceptance remains deferred to noncontact_acceptance until TARGET_ACCURACY_BUDGET_CLOSED."
            if row["record_id"] == "INT-005"
            else "This source requirement is not an observed value. Recording a draft does not assess or accept this question."
        )

    def show_physical_intake_evidence(
        self, projection: Any, view: dict[str, Any]
    ) -> None:
        self.write("Retained passive intake evidence")
        self.write("BYTES / PROCEDURAL REVIEW ONLY")
        self.write(
            "The source verdict remains BLOCKED. OBSERVED means operator-reported, not measurement truth. File integrity and distinct labels do not qualify hardware or authenticate independent people. INT-005 acceptance stays deferred to noncontact_acceptance."
        )
        value = _PhysicalIntakeEvidenceDisplay.projection(projection, view)
        if value is None:
            self.write(
                "No retained intake projection in this snapshot. Nothing is submitted or discovered by viewing it."
                if projection is None
                else "PHYSICAL_INTAKE_EVIDENCE_NOT_VERIFIED: Inconsistent, unsupported or stale cached context withheld. Inspect original diagnostics; no retry or acceptance is inferred."
            )
            return
        self.write(
            f"Intake publication: {value['publication']['status']} / {value['status']}"
        )
        self.write(value["meaning"])
        if value["publication"]["status"] == "PENDING":
            self.write(
                "Publication pending: discovery and collection details withheld until original-store retention and completion logging succeed."
            )
            return
        if (
            value["status"] == "HISTORICAL_HELD"
            or value["publication"]["status"] == "HISTORICAL_HELD"
        ):
            self.write(
                "HISTORICAL ONLY: original subject context is not current qualification or a usable file choice. No automatic discovery, submission, review or replay."
            )
        if value["original_context"] is not None:
            self.write(value["original_context"])
        d = value["discovery"]
        self.write("Assigned inbox — explicit discovery only")
        self.write(d["directory"])
        self.write({k: d[k] for k in ("status", "discovery_sha256")})
        self.write(
            "Place files in the assigned inbox, then explicitly discover. Complete all sixteen draft questions. OBSERVED requires an attachment; UNKNOWN may omit one. Batch selection does not read files or submit automatically."
        )
        for file in d["files"]:
            self.write(
                f"{file['basename']} · {file['media_type']} · {file['payload_bytes']} bytes · {file['payload_sha256']}"
            )
        for issue in d["issues"]:
            self.write(f"{issue['basename'] or 'Assigned inbox'}: {issue['code']}")
        c = value["collection"]
        if c is None:
            self.write(
                "No published collection. Draft notes are not stored attachment evidence."
            )
        else:
            self.write("Latest original collection")
            self.write(
                {
                    "collection_id": c["collection_id"],
                    "collection_state": c["state"],
                    "retained_collection_count": value["collection_count"],
                }
            )
            if c["state"] in ("INCOMPLETE", "REVIEW_RETAINED_NOT_COMMITTED"):
                self.write(
                    "Incomplete publication: stored bytes or review are not a committed review. Inspect the original collection; do not silently retry."
                )
            s = c["submission"]
            if s is not None:
                self.write(
                    {
                        k: s[k]
                        for k in (
                            "submission_sha256",
                            "sequence",
                            "predecessor_submission_sha256",
                            "operator_id",
                            "notebook_revision",
                            "binding",
                        )
                    }
                )
                self.write("Reported coverage — not measured acceptance")
                self.write(s["coverage"])
                for row in s["rows"]:
                    self.write(
                        f"{row['record_id']}: {row['measurement']} / {row['unit'] or 'no unit'} / {row['status']} / {row['acceptance_status']}"
                    )
                    for key in (
                        "observed_value",
                        "method",
                        "attachment_evidence_id",
                        "acceptance_owner_stage",
                    ):
                        self.write(
                            f"{key}: {'No attachment' if row[key] is None else row[key]}"
                        )
                for file in s["attachments"]:
                    self.write(
                        f"Retained original: {file['evidence_id']} · {file['basename']} · {file['media_type']} · {file['payload_bytes']} bytes · {file['payload_sha256']}"
                    )
            if c["assessment"] is not None:
                self.write("Structure/reference assessment — physical readiness false")
                self.write(
                    {
                        k: c["assessment"][k]
                        for k in (
                            "assessment_sha256",
                            "status",
                            "observation_completeness",
                            "unknown_record_ids",
                        )
                    }
                )
            if c["review"] is not None:
                self.write("Exact-subject procedural review — not authenticated people")
                self.write(
                    {
                        k: c["review"][k]
                        for k in (
                            "reviewer_id",
                            "review_sha256",
                            "submission_sha256",
                            "assessment_sha256",
                            "decision",
                            "review_launch_id",
                        )
                    }
                )
                self.write(
                    "Submission REJECTED; original evidence remains retained."
                    if c["review"]["decision"] == "REJECT"
                    else "Acknowledged for later-stage review only. No canonical physical stage is accepted."
                )
        self.write(
            "Diagnostics export retains submission metadata, not original media. Export originals is a separate explicit action: byte-preserving files may contain private material and are not redacted. This page does not open or preview attachments."
        )

    def show_usb_qualification(self, projection: Any, view: dict[str, Any]) -> None:
        self.write("USB reconnect / reboot trial — original phases")
        value = _UsbQualificationDisplay.validate(projection, view)
        if value is None:
            self.write(
                "No trial declaration is included in this older snapshot."
                if projection is None
                else "USB_QUALIFICATION_NOT_VERIFIED: Unsupported or inconsistent original declaration; no qualification is inferred."
            )
            return
        self.write(
            {
                k: value[k]
                for k in ("status", "publication", "source_sha256", "launch_session_id")
            }
        )
        self.write(value["meaning"])
        if value["publication"]["status"] == "PENDING":
            self.write(
                "Original phase publication pending; plan and observation details are withheld until original readback and the completion log."
                if value["schema"]
                in {
                    "rocell.wizard_usb_qualification.v2",
                    "rocell.wizard_usb_qualification.v3",
                    "rocell.wizard_usb_qualification.v4",
                    "rocell.wizard_usb_qualification.v5",
                }
                else "Declaration publication pending; plan details are withheld until original readback and the completion log."
            )
            return
        if value["publication"]["status"] != "CURRENT":
            self.write(
                "HISTORICAL ONLY: This declaration does not restore a permit or trigger any acquisition."
            )
        if value["next_action"] == "physical_camera_refresh":
            enabled = any(
                action.get("action_id") == "physical_camera_refresh"
                and action.get("enabled") is True
                for action in view.get("actions", [])
            )
            self.write(
                "Three current-launch metadata acquisitions are logged after this phase’s operator report. "
                + (
                    "Next explicit action: physical_camera_refresh. Use its eligible form to recheck the original session before Prepare."
                    if enabled
                    else "Original-session refresh is required before Prepare; inspect the server's current action hold."
                )
                + " Refresh performs no boot or USB query and does not renew or replay an attempted interval."
            )
        plan = value["plan"]
        if plan is not None:
            self.write(
                {
                    "trial_id": plan["binding"]["trial_id"],
                    "plan_sha256": plan["plan_sha256"],
                    "original_launch": plan["binding"]["origin_launch_id"],
                    "declaring_launch": plan["launch_session_id"],
                }
            )
            self.write(f"Operator label: {plan['operator_id']}")
            self.write(f"Declared cable: {plan['cable_label']}")
            self.write(f"Declared host port: {plan['port_label']}")
            for key in ("manufacturer", "product_id", "serial"):
                self.write(f"Original received {key}: {plan['received_label'][key]}")
            phase_keys = {
                "BASELINE": "baseline",
                "RECONNECT_ABSENCE": "absence",
                "AFTER_RECONNECT": "reconnect",
                "AFTER_REBOOT": "reboot",
            }
            for phase in plan["phases"]:
                state = (value.get(phase_keys[phase]) or {}).get("state")
                self.write(
                    f"{phase}: {state or 'NOT ACQUIRED — required future phase, not evidence.'}"
                )
        baseline = value.get("baseline")
        if baseline:
            self.write(
                {
                    k: baseline[k]
                    for k in ("phase_id", "state", "phase_start_event_sha256")
                }
            )
            self.write(
                "Acquisition rows are published only after exact result retention and completion logging. Refresh the original session after fresh metadata review; timestamps are not device attestation."
            )
            rows = (baseline["acquisition_ledger"] or {}).get("entries", [])
            for role in ("GENERIC_INVENTORY", "NATIVE_INVENTORY", "NATIVE_IDENTITY"):
                row = next((r for r in rows if r["role"] == role), None)
                self.write(
                    f"{role}: "
                    + (
                        "NOT ACQUIRED IN THIS PHASE"
                        if row is None
                        else "LOGGED IN THIS PHASE — " + row["operation_id"]
                    )
                )
            if baseline["target"]:
                self.write(baseline["target"])
            if baseline["preparation"]:
                self.write(
                    f"Prepared by {baseline['preparation']['operator_id']}; original preparation {baseline['preparation']['preparation_sha256']}"
                )
            if baseline["review"]:
                self.write(
                    f"Reviewed by {baseline['review']['reviewer_id']}; boot request {baseline['review']['boot_request_sha256']}. Labels are not authenticated independent people."
                )
            if baseline["host_boot"]:
                self.write(baseline["host_boot"])
                self.write(
                    "LastBootUpTime is provider-reported, not attestation. A new app launch is not a reboot."
                )
                if baseline["host_boot"]["blockers"] or baseline["host_boot"][
                    "original_state"
                ] in {"BOOT_HELD", "BOOT_UNCERTAIN"}:
                    self.write(
                        "Export the retained host-boot request, process diagnostics and original events. USB collection did not follow an unconfirmed boot result; do not retry or infer a reboot from this launch."
                    )
            if baseline["execution"]:
                execution = baseline["execution"]
                self.write(execution)
                self.write(
                    "Hub open attempts: "
                    + (
                        "UNKNOWN"
                        if execution["actual_counts"] is None
                        else str(execution["actual_counts"]["hub_open_attempts"])
                    )
                )
                if (
                    not execution["process_cleanup_confirmed"]
                    or not execution["usb_cleanup_confirmed"]
                ):
                    self.write(
                        "Cleanup or effect accounting is unconfirmed. Do not retry or assume the device is closed; export retained originals."
                    )
            if baseline["observation"]:
                self.write(baseline["observation"])
            if baseline["phase_record"]:
                for check in baseline["phase_record"]["checks"]:
                    self.write(
                        check["check_id"]
                        + ": "
                        + (
                            "OBSERVED CHECK ONLY"
                            if check["passed"]
                            else "NOT ESTABLISHED"
                        )
                    )
        absence = value.get("absence")
        if absence:
            self.write("RECONNECT_ABSENCE — exact physical USB node")
            self.write(
                {
                    k: absence[k]
                    for k in ("phase_id", "state", "phase_start_event_sha256")
                }
            )
            self.write(
                "The unplug report is not proof of mechanical cause or continuous absence. No live camera endpoint is selected after unplugging. Stop is software cancellation, not a robot emergency stop."
            )
            for key in (
                "target",
                "operator_event",
                "preparation",
                "boot_review",
                "host_boot",
                "runtime_review",
            ):
                if absence[key] is not None:
                    self.write({key: absence[key]})
            boot = absence["host_boot"]
            if boot is not None:
                self.write(
                    "LastBootUpTime is provider-reported, not attestation. A new application launch is not a reboot; changed boot during unplugging is a hold."
                )
                if boot["original_state"] != "BOOT_RETAINED":
                    self.write(
                        "Presence query did not follow this held/uncertain boot. Export the original intent, report and events; do not retry."
                    )
            execution = absence["execution"]
            if execution is not None:
                self.write("Owned physical-node query — not USB hub opens")
                self.write(execution)
                for key in (
                    "api_calls",
                    "device_handle_opens",
                    "configuration_writes",
                    "frames",
                ):
                    self.write(
                        key
                        + ": "
                        + (
                            "UNKNOWN"
                            if execution["actual_counts"] is None
                            else str(execution["actual_counts"][key])
                        )
                    )
                if (
                    not execution["process_cleanup_confirmed"]
                    or not execution["native_cleanup_confirmed"]
                    or execution["counter_coverage"] == "NOT_REPORTED"
                ):
                    self.write(
                        "Unknown or unconfirmed effects remain held. Export the original campaign and process evidence; never replay this request."
                    )
            elif absence["state"] in {
                "QUERY_REQUESTED",
                "ORIGINAL_CAMPAIGN_HELD",
            } or (
                absence["state"] == "INCOMPLETE"
                and absence["runtime_review"] is not None
            ):
                self.write("Physical-node query evidence unavailable")
                self.write("counter_coverage: NOT_REPORTED")
                for key in (
                    "api_calls",
                    "device_handle_opens",
                    "configuration_writes",
                    "frames",
                ):
                    self.write(key + ": UNKNOWN")
                self.write(
                    "No owned execution evidence is available for this retained request or partial attempt. Do not infer that the query did not run or that effects were zero. Export the original campaign and terminal reasons; do not replay this request."
                )
            if absence["observation"] is not None:
                self.write(absence["observation"])
            if absence["phase_record"] is not None:
                self.write(absence["phase_record"])
            self.write(
                "ABSENT means two complete request-bound physical-node samples only. An absence result does not replace AFTER_RECONNECT or AFTER_REBOOT; no qualification PASS or capture/arm release follows this phase."
            )
        for phase_name, reconnect in (
            ("AFTER_RECONNECT", value.get("reconnect")),
            ("AFTER_REBOOT", value.get("reboot")),
        ):
            if reconnect is None:
                continue
            reboot = phase_name == "AFTER_REBOOT"
            self.write(phase_name + " — retained original interval")
            self.write(
                {
                    key: reconnect[key]
                    for key in ("phase_id", "state", "phase_start_event_sha256")
                }
            )
            self.write(
                "The restart report is an operator statement, not reboot evidence. Every metadata acquisition must be logged after this new report; no acquisition or restart runs automatically."
                if reboot
                else "The reconnect report is an operator statement, not mechanical proof. Every metadata acquisition must be logged after that report. A new app launch does not renew this interval."
            )
            for key in (
                "operator_event",
                "target",
                "preparation",
                "review",
                "host_boot",
            ):
                if reconnect[key] is not None:
                    self.write({key: reconnect[key]})
            for row in (reconnect["acquisition_ledger"] or {}).get("entries", []):
                self.write(
                    f"{row['role']}: LOGGED AFTER RECONNECT REPORT — {row['operation_id']}"
                )
            boot = reconnect["host_boot"]
            if boot is not None:
                self.write(
                    "LastBootUpTime is provider-reported, not attestation. Reboot requires the same host, a different boot and an epoch after reconnect completion and no later than Begin. Boot collection does not automatically query USB."
                    if reboot
                    else "LastBootUpTime is provider-reported, not attestation; reconnect requires the same original host and boot. Boot collection does not automatically query USB."
                )
                for issue in boot["blockers"]:
                    self.write("Host-boot hold: " + issue)
                if boot["original_state"] != "BOOT_RETAINED":
                    self.write(
                        "No descriptor query follows this held or uncertain boot. Export the retained intent, report and original events; do not retry."
                    )
            execution = reconnect["execution"]
            if execution is not None:
                self.write(
                    "Owned "
                    + ("reboot" if reboot else "reconnect")
                    + " descriptor query"
                )
                self.write(execution)
                counts = execution["actual_counts"]
                self.write(
                    "Hub open attempts: "
                    + (
                        "UNKNOWN"
                        if counts is None
                        else str(counts["hub_open_attempts"])
                    )
                )
                self.write(reconnect["observation"])
            elif reconnect["state"] in {
                "QUERY_REQUESTED",
                "ORIGINAL_CAMPAIGN_HELD",
            } or (
                reconnect["state"] == "INCOMPLETE" and reconnect["review"] is not None
            ):
                self.write(
                    "Descriptor query evidence unavailable: counter_coverage NOT_REPORTED; hub opens UNKNOWN. Do not infer no query or zero effects. Export original campaign reasons; never replay the request."
                )
            final = reconnect["phase_record"]
            if final:
                self.write(
                    {
                        key: final[key]
                        for key in ("phase_sha256", "status", "boot_relation")
                    }
                )
                for row in final["comparisons"]:
                    item = final["values"][row["field"]]
                    shown = (
                        item["value"]
                        if item["status"] == "VALUE_RETAINED"
                        else item["status"]
                    )
                    self.write(
                        f"{row['field']}: {shown} / {row['status']} / original SHA {item['sha256']}"
                    )
                for check in final["checks"]:
                    self.write(
                        f"{check['check_id']}: {'OBSERVED CHECK ONLY' if check['passed'] else 'NOT ESTABLISHED'}"
                    )
            self.write(
                "Four phase records alone are not stage PASS or capture/arm release. See the separate final identity review below when present. Stop is software cancellation, not a robot E-stop."
                if reboot
                else "Reconnection alone does not complete AFTER_REBOOT or independent final qualification. No reconnect result is stage PASS or capture/arm release. Reopened or uncertain work is export-only. Stop is software cancellation, not a robot E-stop."
            )
        if value.get("schema") == "rocell.wizard_usb_qualification.v6":
            self.write("Final camera-identity review — files only")
            complete = value["complete"]
            if complete is None:
                self.write(
                    "All four original phases are available for explicit assessment. No assessment or acceptance has been recorded."
                )
            else:
                self.write(
                    {
                        key: complete[key]
                        for key in (
                            "series_id",
                            "state",
                            "series_sha256",
                            "assessment_sha256",
                            "review_sha256",
                        )
                    }
                )
                if complete["assessment"] is not None:
                    self.write("Assessment: " + complete["assessment"]["verdict"])
                    for check in complete["assessment"]["missing_requirements"]:
                        self.write("NOT ESTABLISHED: " + check)
                if complete["review"] is not None:
                    self.write(complete["review"])
                self.write(
                    "A retained review file is not a committed PASS. Partial evidence is export-only; do not replay the action."
                )
            self.write(
                "Identity acceptance does not authorize camera capture, arm access, power, motion or contact. Reviewer labels do not authenticate independent people."
            )
        self.write(
            "A new app launch is not a reboot. The standalone legacy baseline cannot fill a declared trial phase. Manual disconnect/reconnect and Windows Restart are not performed automatically; declaration grants no phase or capture release."
        )
        if value["export_receipt"] is not None:
            self.write(
                f"Separate original USB export: {value['export_receipt']['path']}"
            )
            self.write(
                f"Manifest SHA-256: {value['export_receipt']['manifest_sha256']}"
            )

    def show_usb_identity(self, projection: Any, view: dict[str, Any]) -> None:
        self.write("USB identity — one original baseline")
        self.write(
            "Fixed-file inspection/review are file-only. Collection is a separate explicitly confirmed USB descriptor query: no camera capture, arm access, power, motion or contact. Baseline is not reconnect/reboot qualification."
        )
        value = _UsbIdentityDisplay.validate(projection, view)
        if value is None:
            self.write(
                "No USB baseline workflow is available in this snapshot."
                if projection is None
                else "USB_IDENTITY_NOT_VERIFIED: Unsupported or inconsistent cached context; no query or qualification is inferred."
            )
            return
        self.write(
            {
                k: value[k]
                for k in ("status", "publication", "source_sha256", "launch_session_id")
            }
        )
        self.write(value["meaning"])
        if value["publication"]["status"] == "PENDING":
            self.write(
                "USB publication pending: new target, review and query observations withheld until original retention and completion logging."
            )
            return
        pointer = value["schema"] == "rocell.wizard_usb_identity_export_pointer.v1"
        data = value["coverage"] if pointer else value
        if pointer:
            self.write(
                "General export coverage only — full original USB evidence requires the separate metadata bundle."
            )
        if value["publication"]["status"] != "CURRENT":
            self.write(
                "HISTORICAL ONLY: Original target and USB observations are not a current connection. Reopen/refresh does not query, restore a consumed grant or replay this attempt."
            )
        self.write({"original_context": value["original_context"]})
        if data["inspection"] is not None:
            self.write("Fixed files and exact target")
            self.write(data["inspection"])
        if data["review"] is not None:
            self.write(
                "Exact policy/runtime review — labels are not authenticated independent people; file review is not hardware qualification."
            )
            self.write(data["review"])
        e = data["execution"]
        if e is not None:
            self.write("Owned query outcome and separate process / USB cleanup")
            self.write(e)
            if e["provenance"] == "INCAPABLE_USB_QUERY":
                self.write(
                    "INCAPABLE / MODELED USB OBSERVATIONS — no received hardware was queried."
                )
            if e["actual_counts"] is None:
                self.write(
                    "Actual USB counts: NOT REPORTED / UNKNOWN. They are not zero; cleanup cannot be inferred from process exit."
                )
        if data["observation"] is not None:
            self.write("Literal retained USB values — not inferred identity")
            self.write(data["observation"])
            self.write(
                "Only independent V2 operating flags describe SuperSpeed operation. EX speed/capability are not substituted; no nominal Mbps or serial is inferred."
            )
        if e is not None:
            if (
                not e["process_cleanup_confirmed"]
                or e["counter_coverage"] == "NOT_REPORTED"
                or (
                    e["counter_coverage"] == "NATIVE_RECEIPT"
                    and not e["usb_cleanup_confirmed"]
                )
            ):
                self.write(
                    "Cleanup or effect accounting is uncertain. Do not retry or assume the device is closed. Export the retained original process/USB evidence and investigate both cleanup records before any new attempt."
                )
            if re.search(
                r"SOURCE|CONTEXT|TARGET|IDENTITY|PIN|FILE|RUNTIME", e["error"] or ""
            ):
                self.write(
                    "Compare the retained source, runtime pins and exact target with the original reviewed subject. Changed files or selection require a new explicitly eligible inspection/review; never substitute a target or replay the consumed operation."
                )
            if e["status"] in {"CANCELLED", "TIMED_OUT"}:
                self.write(
                    "The original Stop/deadline remains part of this attempt. Inspect and export its retained outcome; restarting the app does not renew its budget or authorize retry."
                )
        o = data["observation"]
        if (
            o is not None
            and o["operating_at_superspeed"] is not True
            and o["operating_at_superspeed_plus"] is not True
        ):
            self.write(
                "USB3 operation is not established by these observations. Review the exact V2 operating flags and physical USB path; advertised capability or EX speed cannot fill this gap."
            )
        if value["export_receipt"] is not None:
            self.write(
                {
                    k: value["export_receipt"][k]
                    for k in ("path", "export_id", "manifest_sha256")
                }
            )
        if not pointer and value["next_action"] is not None:
            matches = [
                a
                for a in view.get("actions", [])
                if a.get("action_id") == value["next_action"]
                and a.get("enabled") is True
            ]
            if len(matches) == 1:
                self.write(
                    "Next explicit eligible form: "
                    + value["next_action"]
                    + ". Nothing is prepared or executed by this display."
                )
        self.write(
            "One-shot attempt: Stop cannot undo completed queries or committed evidence. Await cleanup, export held evidence, and do not automatically retry. Physical absence/reconnect/actual same-host reboot remain separate missing work; a new app launch is not a reboot."
        )

    def show_camera_identity(self, projection: Any, view: dict[str, Any]) -> None:
        self.write("Original camera identity — stage 4")
        self.write(
            "Metadata-only assessment remains BLOCKED. No complete persistent-unit identity, USB operating-speed or reconnect/reboot qualification, stage-5 entry, native capture release or current connection is established."
        )
        value = _CameraIdentityDisplay.validate(projection, view)
        if value is None:
            self.write(
                "No original identity workflow is available in this snapshot."
                if projection is None
                else "CAMERA_IDENTITY_NOT_VERIFIED: Inconsistent cached identity context or publication withheld. No acceptance is inferred."
            )
            return
        self.write(
            {
                key: value[key]
                for key in (
                    "status",
                    "publication",
                    "source_sha256",
                    "launch_session_id",
                )
            }
        )
        self.write(value["meaning"])
        if value["schema"] == "rocell.wizard_camera_identity_export_pointer.v1":
            self.write(
                "IDENTITY METADATA POINTER ONLY: General export covers hashes; full original subjects require the separate physical_camera_identity_export bundle."
            )
            self.write({key: value[key] for key in ("cycles", "export_receipt")})
            return
        if value["publication"]["status"] == "PENDING":
            self.write(
                "Identity publication pending: new subjects withheld until original readback, source/Stop checks and completion logging."
            )
            return
        historical = value["publication"]["status"] != "CURRENT"
        if historical:
            self.write(
                "HISTORICAL ONLY: Original metadata is not current device identity. No inventory, live endpoint restoration or submission replay occurs on refresh/reopen."
            )
        for key in ("original_context", "stage_states"):
            if value[key] is not None:
                self.write({key: value[key]})
        for cycle in value["cycles"]:
            self.write(
                f"Identity collection {cycle['sequence']}: {cycle['state']} | {cycle['identity_id']}"
            )
            for role in _CameraIdentityDisplay.IDENTITY_ROLES:
                self.write(
                    f"{role}: {cycle[role]['sha256'] if cycle[role] else 'NOT_RETAINED'}"
                )
            a = cycle["assessment"]
            if a is not None:
                self.write("Metadata checks — not qualification")
                for key, item in a["checks"].items():
                    if key == "driver_field_availability":
                        for name, status in item.items():
                            self.write(f"Exact-devnode driver {name}: {status}")
                    else:
                        self.write({key: item})
                self.write("Missing qualification evidence — BLOCKED")
                for reason in a["missing_requirements"]:
                    self.write(reason)
            if cycle["review"] is not None:
                self.write(
                    "Exact-subject procedural review cannot upgrade BLOCKED. Original INT-018 statement and actor labels remain in the full bundle; they are not authenticated identities."
                )
        if not value["cycles"]:
            self.write(
                "No original identity collection retained. Explicit metadata discovery/reviews and original-store refresh are required; INT-018 must record an observation or UNKNOWN reason. No serial is inferred."
            )
        if value["next_action"] is not None and not historical:
            self.write(
                f"Next explicit action: {value['next_action']}. Nothing is selected automatically."
            )
        if value["export_receipt"] is not None:
            self.write("Separate identity metadata export")
            self.write(
                {
                    key: value["export_receipt"][key]
                    for key in ("path", "export_id", "manifest_sha256")
                }
            )
        self.write(
            "General diagnostics carry coverage only. Export the separate complete identity metadata bundle; private raw media is not included."
        )

    def show_received_camera(self, projection: Any, view: dict[str, Any]) -> None:
        self.write("Received camera and passive workcell — original records")
        value = _ReceivedCameraDisplay.validate(projection, view)
        if value is None:
            self.write(
                "No received-camera collection is available. Explicitly begin after reviewed static design."
                if projection is None
                else "RECEIVED_CAMERA_NOT_VERIFIED: Inconsistent or unsupported retained metadata withheld; no acceptance or replay is inferred."
            )
            return
        self.write(
            {
                key: value[key]
                for key in (
                    "status",
                    "publication",
                    "source_sha256",
                    "launch_session_id",
                )
            }
        )
        self.write(value["meaning"])
        if value["schema"] == "rocell.wizard_received_camera_export_pointer.v1":
            self.write(
                "RECEIVED METADATA POINTER ONLY: General diagnostics do not contain original received-camera documents or private media. Use the separate physical_received_camera_export bundle."
            )
            for key in ("latest_subjects", "metadata_export"):
                if value[key] is not None:
                    self.write({key: value[key]})
            return
        if value["publication"]["status"] == "PENDING":
            self.write(
                "Publication pending: draft, original collection and file choices withheld until original-store readback and completion logging succeed."
            )
            return
        historical = value["publication"]["status"] != "CURRENT"
        if historical:
            self.write(
                "HISTORICAL ONLY: Original observations and reviewer labels are not current qualification. No automatic retry or identity entry."
            )
        for key in ("original_context", "stage_states"):
            if value[key] is not None:
                self.write({key: value[key]})

        def notebook(book, title):
            self.write(title)
            self.write({key: book[key] for key in ("revision", "binding", "coverage")})
            for row in book["rows"]:
                self.write(
                    {
                        "record_id": row["record_id"],
                        "measurement": row["measurement"],
                        "source_unit": row["unit"],
                        "observation_status": (
                            "UNRECORDED"
                            if row["observation"] is None
                            else row["observation"]["status"]
                        ),
                    }
                )
                self.show_intake_question(row)
                if row["observation"] is None:
                    self.write(
                        "No observation recorded. No numeric value or identity is inferred."
                    )
                else:
                    self.write(
                        {
                            key: item
                            for key, item in row["observation"].items()
                            if key != "recorded_at_ns"
                        }
                    )
                    self.write(
                        "Original record time retained; not interpreted as freshness or measurement truth."
                    )

        if value["draft"] is not None:
            notebook(
                value["draft"],
                (
                    "Editable draft — not a stored receipt"
                    if not historical
                    else "Historical draft — not a stored receipt"
                ),
            )
            if value["draft_origin_notebook_sha256"]:
                self.write(
                    {
                        "carried_from_original_notebook": value[
                            "draft_origin_notebook_sha256"
                        ]
                    }
                )
                self.write(
                    "Carried-forward observations preserve original labels and timestamps; they are not fresh measurements. Structured inspection must be explicitly observed again."
                )
        collection = value["collection"]
        if collection is not None:
            self.write("Latest original received collection")
            self.write(
                {key: collection[key] for key in ("receipt_id", "sequence", "state")}
            )
            if collection["notebook"] is not None:
                notebook(
                    collection["notebook"]["document"],
                    "Original retained notebook — exact subject for review",
                )
            submission, assessment, review, inspection = (
                collection[key]
                for key in ("submission", "assessment", "review", "inspection")
            )
            if submission:
                self.write(
                    {
                        key: submission[key]
                        for key in (
                            "submission_sha256",
                            "notebook_sha256",
                            "inspection_sha256",
                            "attachment_count",
                            "attachment_bytes",
                            "linked_row_count",
                            "carried_forward_record_ids",
                        )
                    }
                )
                self.write(
                    "Submission operator label: " + submission["binding"]["operator_id"]
                )
            self.write("Structured received-camera inspection — operator reported")
            if inspection:
                self.write(
                    {
                        key: inspection[key]
                        for key in (
                            "observed_manufacturer",
                            "observed_product_id",
                            "observed_camera_serial",
                            "observed_lens_focal_length_mm",
                            "body_condition",
                            "lens_condition",
                            "connector_condition",
                            "identity_label_legible",
                            "purchase_record_matches",
                            "package_contents_complete",
                            "inspection_uncertain",
                            "receipt_sha256",
                            "purchase_record_evidence_id",
                            "inspection_image_evidence_ids",
                        )
                    }
                )
                self.write(
                    "Original media is referenced, never opened or previewed here. Narrative notes do not replace structured identity or prove measurement truth."
                )
            else:
                self.write(
                    "Structured inspection UNKNOWN / not retained. Manufacturer, serial and lens identity are not inferred from notebook prose."
                )
            if assessment:
                self.write("Receipt completeness assessment: " + assessment["verdict"])
                self.write(
                    {
                        "assessment_sha256": assessment["assessment_sha256"],
                        "foundation_sha256": assessment["foundation_sha256"],
                        "status": assessment["foundation"]["status"],
                        "coverage": assessment["foundation"]["coverage"],
                    }
                )
                self.write("Recorded thickness accommodation — exact decimal text")
                self.write(assessment["foundation"]["thickness"])
                for item in (
                    *assessment["missing_requirements"],
                    *assessment["foundation"]["residuals"],
                ):
                    self.write(item)
            if review:
                self.write("Exact-subject receipt review")
                self.write("Reviewer label: " + review["reviewer_id"])
                self.write(
                    {
                        key: review[key]
                        for key in (
                            "review_sha256",
                            "submission_sha256",
                            "assessment_sha256",
                            "decision",
                            "verdict",
                            "review_launch_id",
                        )
                    }
                )
                self.write(
                    "Distinct labels are procedural, not authenticated independent people. Original review time is retained, not a freshness proof."
                )
            else:
                self.write(
                    "No committed exact-subject review; retained bytes or an assessment alone are not a stage PASS."
                )
        if value["status"] == "REVIEWED_PASS" and not historical:
            self.write(
                "Stage 3 receipt accepted only — no installation qualification or native camera release."
            )
            self.write(
                "Stage 4 identity was explicitly requested and remains WAITING_OPERATOR; no metadata enumeration has occurred."
                if value["identity_entry"]
                else "Stage 4 remains PENDING. Identity entry requires a separate explicit action."
            )
        discovery = value["inbox"]["discovery"]
        self.write("Assigned inbox — explicit file discovery")
        self.write(
            {key: discovery[key] for key in ("directory", "status", "discovery_sha256")}
        )
        for item in (*discovery["files"], *discovery["issues"]):
            self.write(item)
        if value["identity_entry"]:
            self.write({"identity_entry_event": value["identity_entry"]})
        if value["metadata_export"]:
            self.write("Separate received metadata export")
            self.write(
                {
                    key: value["metadata_export"][key]
                    for key in ("path", "export_id", "manifest_sha256")
                }
            )
        if value["next_action"] and not historical:
            self.write(
                "Next explicit action: "
                + value["next_action"]
                + ". Viewing never prepares or executes it."
            )
        self.write(
            "INT-005 acceptance remains deferred. No invented mounting, C/CS, bench, nominal-dimension or mass tolerances. Export received-camera metadata separately; general diagnostics contain a pointer only. Private original media is not included or opened."
        )

    def show_physical_intake(self, projection: Any, setup: Any) -> None:
        self.write("Passive intake notebook: DRAFT ONLY / NOT ACCEPTED")
        self.write(
            "No stage PASS, power observation, epoch, permit or connection is created. Evidence notes are descriptions only; no attachment bytes are uploaded, read or verified. Export the notebook to the assigned diagnostics folder before closing: draft restoration on another launch is not supported."
        )
        value = _PhysicalIntakeDisplay.validate(projection, setup)
        if value is None:
            self.write(
                "No intake notebook is available. Start explicitly after current setup requirements are published."
                if projection is None
                else "PHYSICAL_INTAKE_NOT_VERIFIED: Inconsistent, stale or unsupported draft withheld. Nothing is inferred from old observations."
            )
            return
        self.write({"status": value["status"]})
        self.write(value["meaning"])
        n = value["notebook"]
        if n is None:
            self.write(
                "Current draft is held. Retained exports are historical drafts, not current measurement or acceptance."
                if value["status"] == "HISTORICAL_HELD"
                else "No notebook started. Candidate dimensions never populate observation fields automatically."
            )
            return
        self.write(
            {
                key: n[key]
                for key in ("revision", "snapshot_sha256", "previous_sha256", "binding")
            }
        )
        self.write("Draft coverage - not measurement acceptance")
        self.write(n["coverage"])
        self.write(
            "OBSERVED means operator-reported, not verified. UNKNOWN is a reason, not measured coverage. Enter a value or reason, method, evidence description and operator explicitly; use your own 'not measured' or 'not supplied' description when appropriate. Narrative descriptions must be single-line, without line breaks. No nominal defaults or autosave."
        )
        for row in n["rows"]:
            observation = row["observation"]
            self.write(
                {
                    "record_id": row["record_id"],
                    "measurement": row["measurement"],
                    "source_unit": row["unit"],
                    "draft_status": (
                        "UNRECORDED" if observation is None else observation["status"]
                    ),
                    "acceptance": "NOT ACCEPTED",
                }
            )
            self.show_intake_question(row)
            if observation is not None:
                self.write(
                    {
                        key: item
                        for key, item in observation.items()
                        if key != "recorded_at_ns"
                    }
                )
                self.write(
                    "Record time retained; not interpreted as an exact timestamp or freshness proof."
                )
            else:
                self.write("No operator observation recorded.")

    def show_physical_camera_reopening(self, value: dict[str, Any]) -> None:
        self.write("Discover and reopen original camera storage")
        self.write(
            "Discovery reads bounded store metadata only; it does not qualify or open storage. Reopen explicitly rechecks one selected original store and audits M1 storage. Neither operation connects devices, retries a campaign, repairs a store or clears quarantine. No choice is selected automatically."
        )
        self.write(
            {
                key: value[key]
                for key in (
                    "status",
                    "discovery_sha256",
                    "current_launch_id",
                    "source_sha256",
                )
            }
        )
        self.write(value["meaning"])
        if value["invalidation_reason"]:
            self.write({"invalidation_reason": value["invalidation_reason"]})
        if not value["stores"]:
            self.write(
                "No current selectable store metadata. Use an eligible explicit discovery action; this view does not search for stores."
            )
        for row in value["stores"]:
            self.write(
                "METADATA ONLY / NOT OPENED"
                if row["selectable"]
                else "SOURCE DRIFT / REOPEN HELD"
            )
            self.write(
                "Source match permits only an explicit selected-store recheck. It is not storage acceptance or hardware qualification."
                if row["selectable"]
                else "This original source differs. It has no selectable token and cannot be relabeled as the current build."
            )
            self.write(row)
        if value["issues"]:
            self.write({"store_metadata_issues": value["issues"]})

    def show_physical_configuration_records(self, setup: dict[str, Any]) -> None:
        self.write("Eight-domain configuration records — unqualified dependencies")
        self.write("NO ADMISSION / NO QUALIFICATION")
        if setup["schema"] != "rocell.wizard_physical_camera_setup.v3":
            self.write(
                "NOT_RETAINED: this legacy snapshot has no progressive configuration record. No record was inferred or created."
            )
            return
        value = _PhysicalConfigurationRecordsDisplay.projection(
            setup["configuration_records"], setup
        )
        if value is None:
            self.write(
                "CONFIGURATION_RECORDS_NOT_VERIFIED: inconsistent, unsupported or oversized projection withheld. Original evidence is not replaced or automatically recollected."
            )
            return
        self.write(f"Record publication: {value['status']}")
        if value["status"] == "HISTORICAL_HELD":
            self.write(
                "Historical original configuration context only — not a current observation or acquisition permission."
            )
        s = value["summary"]
        if s is None:
            self.write(
                "Configuration details withheld until explicit operation publication completes. No retained record is inferred from pending work."
                if setup["publication"]["status"] == "PENDING"
                else "No progressive record is available in this snapshot. Refresh does not create missing records or upgrade legacy evidence."
            )
            return
        self.write(
            "Retained references are UNASSESSED, not accepted observations. Pending outputs are not missing predecessors and waive no earlier hazard, isolation, firmware or runtime prerequisite."
        )
        self.write(
            {
                "record_sha256": s["record_sha256"],
                "boundary_stage": s["boundary"]["stage"],
                "boundary_phase": s["boundary"]["phase"],
            }
        )
        self.write(s["binding"])
        self.write("Original recorded boundary — not the latest session head")
        self.write(s["original_snapshot"])
        self.write(s["coverage"])
        self.write(s["meaning"])
        for entry in s["entries"]:
            self.write(f"{entry['epoch_id']}: {entry['status']}")
            self.write(f"Invalidates from: {entry['invalidates_from_stage']}")
            for row in entry["bindings"]:
                self.write(
                    f"{row['binding_id']}: {row['status']} · {row['relative_position']} · producer {row['owner_stage']} · {row['evidence_count']} retained references"
                )
                for digest in row["payload_sha256s"]:
                    self.write(f"payload_sha256: {digest}")
        self.write(
            "The original prerequisite epoch requirements remain UNMEASURED. This immutable record describes its original boundary; later review does not recalculate it. No device control, canonical stage PASS, successor record or automatic retry is provided."
        )

    def show_workspace_source_workflow(self, setup: dict[str, Any]) -> None:
        self.write("Saved workspace-source assessment and review")
        self.write("PHYSICAL ACCEPTANCE BLOCKED")
        self.write(
            "Successful file collection and saved review are not a physical PASS. Disconnected actuator power and HZ-012 qualification are not established by file hashes or consent boxes. No power, device opening, motion or contact is authorized."
        )
        projected = setup.get("source_workflow")
        if projected is None:
            self.write(
                "No source-stage workflow summary is available in this snapshot. Legacy exports remain read-only; no receipt or review is inferred."
            )
            return
        if setup["publication"]["status"] == "PENDING":
            self.write(
                "Source-stage publication pending. Receipt and review details are withheld until original-store audit and completion logging succeed."
            )
            return
        value = _WorkspaceSourceDisplay.projection(projected, setup)
        if value is None:
            self.write(
                "WORKSPACE_SOURCE_WORKFLOW_NOT_VERIFIED: Inconsistent cached subject chain or publication withheld. Inspect original diagnostics; no assessment, review or stage acceptance is inferred."
            )
            return
        self.write(f"Workflow: {value['status']}; power observation: UNKNOWN")
        if value["status"] == "NOT_STARTED":
            self.write(
                "No saved source receipt, assessment or review. Assessment and independent review are separate explicit file-only actions."
            )
        if (
            value["status"] == "HISTORICAL_HELD"
            or setup["publication"]["status"] == "HISTORICAL_HELD"
        ):
            self.write(
                "Historical original source evidence only; not a current audited stage result. Preserve the original subject chain. Do not recollect, replay or relabel a receipt to clear this hold."
            )
        receipt, assessment, review = (
            value["receipt"],
            value["assessment"],
            value["review"],
        )
        if receipt is not None:
            self.write(
                "Actual retained software facts — separate from missing physical prerequisites"
            )
            for key, item in {
                **receipt["binding"],
                **{
                    key: receipt[key]
                    for key in (
                        "receipt_sha256",
                        "source_file_count",
                        "foundation_contract_count",
                        "host_blocker_count",
                    )
                },
            }.items():
                # Preserve operator labels literally; JSON escaping is not
                # necessary for this already bounded control-free text.
                self.write(f"{key}: {item}")
            self.write(
                f"Current application launch: {setup['launch_session_id']}. Collection launch: {receipt['binding']['collection_launch_id']}. Original storage launch: {receipt['binding']['origin_launch_id']}. Stored authorship is not rewritten on reopen."
            )
            for row in receipt["software_checks"]:
                self.write(
                    f"{row['check_id']}: {'SOFTWARE_CHECK_PASSED' if row['passed'] else 'SOFTWARE_CHECK_BLOCKED'}"
                )
        if assessment is not None:
            self.write("Saved assessment verdict: BLOCKED")
            self.write(f"Assessment: {assessment['assessment_sha256']}")
            self.write("Missing prerequisite evidence")
            for reason in assessment["missing_requirements"]:
                self.write(reason)
        if value["status"] == "REVIEW_PENDING":
            self.write(
                "Original stage is REVIEW_PENDING. A different reviewer must review this exact BLOCKED assessment; no control can change it to PASS."
            )
        if review is not None:
            self.write("Exact-subject independent review — ACKNOWLEDGED_BLOCKED")
            self.write(
                f"Reviewer: {review['reviewer_id']}; review launch: {review['review_launch_id']}"
            )
            self.write(f"Review: {review['review_sha256']}")
            self.write(
                "Distinct labels record procedure, not authenticated independent people. The review acknowledges BLOCKED and cannot upgrade missing physical evidence."
            )
            if value["status"] == "REVIEWED_BLOCKED":
                self.write(
                    f"Original source assessment/review remains BLOCKED. Current supplementary intake stage: {value['supplementary']['state']}. This is a different subject, not a replacement source verdict or a physical PASS."
                    if value["schema"] == "rocell.wizard_workspace_source_workflow.v2"
                    else "Original workspace_sources stage: BLOCKED. Later physical stages remain held; a saved review does not clear isolation or HZ-012 obligations."
                )
        self.write(
            "Export the complete original workflow to the assigned folder. This panel uses cached summaries only: no file collection, M1 readback, assessment, review or device access occurs on render."
        )

    def show_static_camera_onboarding(
        self, projection: Any, view: dict[str, Any]
    ) -> None:
        self.write("Static-camera design and received-unit onboarding")
        self.write(
            "Design-only stage 2 is not received hardware, installation qualification or native camera release. No device, power, motion or contact effect is performed."
        )
        if projection is None:
            self.write(
                "No static-camera onboarding projection in this legacy snapshot. No design acceptance or received unit is inferred."
            )
            return
        value = _StaticCameraOnboardingDisplay.projection(projection, view)
        if value is None:
            self.write(
                "STATIC_CAMERA_ONBOARDING_NOT_VERIFIED: Inconsistent cached design subject or publication withheld. Inspect original diagnostics; no acceptance is inferred."
            )
            return
        self.write(
            f"Status: {value['status']}; publication: {value['publication']['status']}; source: {value['source_sha256']}; current launch: {value['launch_session_id']}"
        )
        self.write(value["meaning"])
        if value["publication"]["status"] == "PENDING":
            self.write(
                "Design publication pending; new contract and entry details remain withheld until original readback and completion logging succeed."
            )
            return
        historical = (
            value["status"] == "HISTORICAL_HELD"
            or value["publication"]["status"] == "HISTORICAL_HELD"
        )
        if historical:
            self.write(
                "Historical design subject only — not current stage acceptance. Original context is not rebound; no replay or automatic next-stage entry."
            )
        for field in ("original_context", "stage_states"):
            if value[field]:
                self.write(
                    "Historical recorded stage states"
                    if historical and field == "stage_states"
                    else field
                )
                for key, item in value[field].items():
                    self.write(f"{key}: {item}")
        contract = value["contract"]
        if contract is None:
            self.write(
                "No complete static contract is published. Use only the eligible explicit file-only action; do not infer received measurements."
            )
        else:
            self.write(
                f"contract_id: {contract['contract_id']}; retained_state: {contract['state']}"
            )
            receipt, assessment, review = (
                contract[key] for key in ("receipt", "assessment", "review")
            )
            if receipt:
                self.write(
                    f"Collection operator label: {receipt['binding']['operator_id']}; receipt_sha256: {receipt['receipt_sha256']}; source_file_count: {receipt['source_file_count']}; source_bytes: {receipt['source_bytes']}"
                )
                self.write(
                    f"Collection launch: {receipt['binding']['collection_launch_id']}; static entry event: {receipt['binding']['static_request_event_sha256']}"
                )
                self.write("Reviewed source qualification dependencies")
                for key, item in receipt["binding"]["source_qualification"].items():
                    self.write(f"{key}: {item}")
                self.write("Published and nominal design values — NOT MEASURED")
                for key, item in receipt["design"].items():
                    if key != "published_mode":
                        self.write(f"{key}: {item}")
                self.write(
                    "Published catalog mode — not selected or observed device settings"
                )
                if receipt["design"]["published_mode"]:
                    for key, item in receipt["design"]["published_mode"].items():
                        self.write(f"{key}: {item}")
                else:
                    self.write("No unique matching published design mode retained.")
                self.write("Actual file-derived design checks")
                for row in receipt["checks"]:
                    self.write(
                        f"{row['check_id']}: {'DESIGN_CHECK_PASSED' if row['passed'] else 'BLOCKED'}"
                    )
                self.write(
                    "Preserved architecture, profile and support qualification holds"
                )
                for family, items in receipt["blockers"].items():
                    for item in items:
                        self.write(f"{family}: {item}")
            if assessment:
                self.write(
                    f"Retained design assessment: {assessment['verdict']}; assessment_sha256: {assessment['assessment_sha256']}"
                )
                for item in assessment["missing_requirements"]:
                    self.write(item)
            if review:
                self.write(
                    f"Exact-subject design review; reviewer label: {review['reviewer_id']}; review_sha256: {review['review_sha256']}; verdict: {review['verdict']}; review launch: {review['review_launch_id']}"
                )
                self.write(
                    "Distinct labels record a procedure, not authenticated independent people. Review timestamp is retained, not interpreted as an exact JavaScript clock."
                )
            else:
                self.write(
                    "A retained assessment alone is not a committed stage PASS; exact-subject review is still required."
                )
        if value["status"] == "REVIEWED_PASS" and not historical:
            self.write(
                "Stage 2 design accepted only — no installation or native camera release."
            )
            self.write(
                "Stage 3 was explicitly requested and remains WAITING_OPERATOR; no received identity or measurement is supplied."
                if value["camera_receipt_entry"]
                else "Stage 3 remains PENDING. Requesting received-camera inspection is a separate explicit action."
            )
        if value["camera_receipt_entry"]:
            self.write(f"camera_receipt_entry_event: {value['camera_receipt_entry']}")
        if value["next_action"] and not historical:
            self.write(
                f"Next explicit action: {value['next_action']}. This display never prepares or executes it."
            )
        self.write(
            "Full original design records share the reserved source metadata export. Private isolation originals are not included; no automatic device activity or replay."
        )

    def show_source_reassessment(self, projection: Any, view: dict[str, Any]) -> None:
        self.write("Workspace-source reassessment — stage-only admission")
        self.write(
            "Source-stage acceptance is not native camera release, received-hardware qualification or permission to connect, energize, move or contact. No device effect is performed by this workflow."
        )
        if projection is None:
            self.write(
                "No source reassessment projection in this legacy snapshot. No successor assessment or accepted stage is inferred."
            )
            return
        value = _SourceReassessmentDisplay.projection(projection, view)
        if value is None:
            self.write(
                "SOURCE_REASSESSMENT_NOT_VERIFIED: Inconsistent cached subject, authority or publication withheld. Inspect original diagnostics; no stage acceptance is inferred."
            )
            return
        self.write(
            f"Status: {value['status']}; publication: {value['publication']['status']}; source: {value['source_sha256']}; current application launch: {value['launch_session_id']}"
        )
        self.write(value["meaning"])
        if value["publication"]["status"] == "PENDING":
            self.write(
                "Reassessment publication pending. New subject details remain withheld until original-store readback, source/Stop checks and completion logging succeed."
            )
            return
        historical = (
            value["status"] == "HISTORICAL_HELD"
            or value["publication"]["status"] == "HISTORICAL_HELD"
        )
        if historical:
            self.write(
                "Historical source qualification subject only — not current stage acceptance. Original observations and actors are not rebound to this launch. No automatic recollection, review or replay."
            )
        if value["original_context"] is not None:
            self.write("Original source context")
            for key, item in value["original_context"].items():
                self.write(f"{key}: {item}")
        if value["stage_states"] is not None:
            self.write(
                "Historical recorded stage states"
                if historical
                else "Original session committed stage states"
            )
            for key, item in value["stage_states"].items():
                self.write(f"{key}: {item}")
        q = value["qualification"]
        if q is None:
            self.write(
                "Incomplete qualification attempt: no complete receipt/assessment pair is projected. Preserve partial original evidence and inspect the full export; do not retry automatically."
                if value["status"] == "INCOMPLETE_HELD"
                else "No complete source qualification is retained. UNKNOWN isolation remains blocked; discovery or a consent checkbox does not observe disconnected power."
            )
        else:
            for key in (
                "qualification_id",
                "collection_launch_id",
                "operator_id",
                "receipt_sha256",
                "assessment_sha256",
            ):
                self.write(f"{key}: {q[key]}")
            self.write("Original BLOCKED source subjects — unchanged")
            for key, item in q["original_subjects"].items():
                self.write(f"{key}: {item}")
            self.write("Actual retained software checks")
            for row in q["software_checks"]:
                self.write(
                    f"{row['check_id']}: {'SOFTWARE_CHECK_PASSED' if row['passed'] else 'SOFTWARE_CHECK_BLOCKED'}"
                )
            self.write(
                "Retained isolation statement — not current electrical telemetry"
            )
            self.write(
                f"State: {q['isolation']['state']}; attachment_sha256: {q['isolation']['attachment_sha256']}; measurement_truth_verified: False"
            )
            self.write(
                q["isolation"]["statement"] or "No isolation statement recorded."
            )
            self.write(
                "An operator statement and original attachment do not authenticate their contents or prove the present electrical state. UNKNOWN cannot satisfy isolation."
            )
            self.write("Stage-relative software ownership coverage")
            self.write(
                f"Status: {q['ownership']['status']}; report_sha256: {q['ownership']['report_sha256']}"
            )
            for row in q["ownership"]["checks"]:
                self.write(
                    f"{row['check_id']}: {'CHECK_PASSED' if row['passed'] else 'HELD'} · {row['provenance']}"
                )
            self.write(
                "Controlled process-start mismatch is fault injection, not observed operating-system PID reuse. Selected-device identity after effectful locking, received-hardware HZ-012 residuals and native runtime release remain separate obligations."
            )
            self.write(f"Retained source assessment verdict: {q['verdict']}")
            for reason in q["missing_requirements"]:
                self.write(reason)
            if q["review"] is not None:
                self.write("Exact-subject source qualification review")
                for key in (
                    "reviewer_id",
                    "review_sha256",
                    "review_launch_id",
                    "verdict",
                ):
                    self.write(f"{key}: {q['review'][key]}")
                self.write(
                    "Distinct labels record a procedure, not authenticated independent people. Review cannot upgrade a BLOCKED assessment."
                )
            else:
                self.write(
                    "Exact-subject review is still required. An assessed PASS is not a committed source-stage PASS."
                )
        if value["status"] == "REVIEWED_PASS" and not historical:
            self.write("Stage 1 accepted only — no camera runtime release.")
            self.write(
                "Stage 2 remains PENDING. Entering the static-camera contract is a separate explicit action; no stage advances on viewing or restart."
                if value["stage_states"]["static_camera_contract"] == "PENDING"
                else "Stage 2 was explicitly requested and remains WAITING_OPERATOR, not accepted. No camera is opened by that request."
            )
        if value["next_action"] is not None and not historical:
            self.write(
                f"Next explicit action: {value['next_action']}. Use its eligible form below; this display never prepares or executes it."
            )
        self.write(
            "Export the full original qualification metadata; original attachment export requires separate privacy consent. This panel reads cached projections only."
        )

    def show_camera_operating_proposal(self, projection: Any, view: Any) -> None:
        from rocell.application.camera_operating_proposal_projection import validate_proposal_projection

        if projection is None:
            return
        value = validate_proposal_projection(
            projection, source_sha256=view.get("source_binding_sha256"),
            launch_session_id=view.get("session_id"),
        )
        if value is None:
            self.write("CAMERA_OPERATING_PROPOSAL_NOT_VERIFIED: Inconsistent status withheld.")
            return
        self.write("Camera operating-mode proposal: DRAFT ONLY — NOT APPROVED")
        self.write(value["state"])
        self.write(value["meaning"])
        if value["proposal"] is not None:
            self.write("Proposal SHA-256: " + value["proposal"]["proposal_sha256"])
            self.write("Policy: " + value["proposal"]["policy_kind"])
        self.write("After recording a draft, use Check proposal against saved original evidence and explicitly select retained captures. That separate file-only assessment does not approve stage 5. Export diagnostics before closing.")

    def show_camera_operating_submission(self, projection: Any, view: Any) -> None:
        from rocell.application.camera_operating_submission_projection import validate_submission_projection

        if projection is None:
            return
        value = validate_submission_projection(projection, source_sha256=view.get("source_binding_sha256"), launch_session_id=view.get("session_id"))
        if value is None:
            self.write("CAMERA_OPERATING_SUBMISSION_NOT_VERIFIED: Inconsistent status withheld.")
            return
        self.write("Camera evidence saved for review: UNREVIEWED — NO CAMERA OR ARM AUTHORITY")
        self.write(value["state"])
        self.write(value["meaning"])
        if value["submission_id"] is not None:
            self.write("Submission SHA-256: " + value["submission_sha256"])
            self.write("Explicit capture requests: " + ", ".join(value["capture_requests"]))
        self.write("Historical pixel checks are not current file verification. Export original submission diagnostics; incomplete writes are never resumed automatically.")

    def show_camera_mode_entry(self, projection: Any, setup_projection: Any) -> None:
        from rocell.application.physical_camera_mode_entry_projection import (
            mode_entry_projection_valid,
        )

        if projection is None:
            return
        self.write("Camera setup entry")
        setup = _PhysicalSetupDisplay.setup(setup_projection)
        if setup is None or not mode_entry_projection_valid(projection, setup):
            self.write(
                "CAMERA_MODE_ENTRY_NOT_VERIFIED: Inconsistent camera-entry display withheld. Inspect/export diagnostics; no automatic retry."
            )
            return
        self.write("NO CAMERA OR ARM ACCESS")
        self.write(
            {key: projection[key] for key in ("status", "publication", "attempted")}
        )
        self.write(projection["meaning"])
        if projection["entry"] is not None:
            self.write("Original setup entry")
            self.write(projection["entry"])
        if projection["attempt"] is not None:
            self.write("Retained attempt")
            self.write(projection["attempt"])
        if projection["next_action"] is not None:
            self.write(
                "Continue to camera setup: use the explicit physical_camera_mode_enter action and review its preview before execution."
            )

    def show_physical_camera_setup(self, projection: Any) -> None:
        self.write("Physical camera setup: NO PHYSICAL AUTHORITY")
        self.write(
            "CURRENT means a published storage/report observation, not physical-stage PASS, a connected camera or native admission. Initialization does not measure hardware or pass any of the 15 physical stages. Refresh audits the original store without replay, repair or quarantine clearing."
        )
        value = _PhysicalSetupDisplay.setup(projection)
        if value is None:
            self.write(
                "No physical setup state is available. Use an eligible explicit initialization action; this view never initializes storage."
                if projection is None
                else "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED: Inconsistent, unsupported or oversized setup projection withheld. Inspect retained diagnostics; nothing is automatically reopened or retried."
            )
            return
        session = value["session"]
        self.write(
            {
                "source_sha256": value["source_sha256"],
                "publication": value["publication"]["status"],
                **{
                    key: session[key]
                    for key in (
                        "status",
                        "operation",
                        "initialize_attempted",
                        "partial_store_possible",
                    )
                },
            }
        )
        self.write(value["meaning"])
        self.write("Assigned original storage binding")
        self.write(session["binding"])
        if value["schema"] in (
            "rocell.wizard_physical_camera_setup.v2",
            "rocell.wizard_physical_camera_setup.v3",
        ):
            self.write(
                "Current application and original storage are distinct identities"
            )
            self.write(
                {
                    "current_application_launch": value["launch_session_id"],
                    "original_storage_launch": value["origin_launch_id"],
                    "requirements_provenance": value["requirements_provenance"],
                }
            )
            self.write(
                "This store belongs to the current launch. No existing store was inferred or selected."
                if value["origin_launch_id"] == value["launch_session_id"]
                else "The original store was explicitly selected for reopening; storage audit and current publication are separate. Its cell, session, source and origin remain unchanged; the current application launch is not a replacement storage session."
            )
            self.show_physical_camera_reopening(value["reopening"])
            if value["requirements_provenance"] == "REOPENED_ORIGINAL_CONTEXT":
                self.write(
                    "Historical original requirements: retained metadata and source-context hashes are not current-launch observations. CURRENT means this original report was audited and published, not current camera identity, configuration, image, connection or received-unit qualification."
                )
        else:
            self.write(
                "Legacy v1 read-only snapshot. Its recorded origin is preserved; a distinct current application launch or restart adoption is not established by this legacy record."
            )
        if session["error"]:
            self.write({"storage_hold": session["error"]})
        verified = session["verification"]
        if verified:
            self.write("Retained storage verification — not hardware qualification")
            self.write(
                {
                    "storage_status": verified["status"],
                    "windows_ntfs_storage_qualified": verified["qualification"][
                        "qualified_windows_ntfs"
                    ],
                    "storage_prechecks_clear_only": verified[
                        "effects_allowed_by_m1_storage"
                    ],
                    "challenge_sha256": verified["challenge_sha256"],
                    "session_header_sha256": verified["session"]["header_sha256"],
                    "session_head_sha256": verified["session"]["head_sha256"],
                    "evidence_inventory_sha256": verified["session"][
                        "evidence_inventory_sha256"
                    ],
                    "absolute_creation_time": "RETAINED_NOT_INTERPRETED_AS_FRESHNESS_PROOF",
                }
            )
            self.write(
                {
                    key: verified[key]
                    for key in ("attempt_ledger", "quarantine", "leases")
                }
            )
            self.write(
                "Original session recorded stage states — not the physical progress checklist"
            )
            self.write(
                "Repeated references are citations in separate committed events, not additional evidence files."
            )
            for row in session["stages"]:
                self.write(
                    {
                        "stage": row["stage"],
                        "recorded_state": row["state"],
                        "evidence_reference_occurrence_count": len(row["evidence_ids"]),
                        "unique_evidence_id_count": len(set(row["evidence_ids"])),
                        "last_event_sequence": row["last_event_sequence"],
                    }
                )
        else:
            self.write(
                "No current storage verification. A partial or held store must be inspected explicitly; a missing report is not an empty successful session."
            )
        self.show_workspace_source_workflow(value)
        self.show_physical_configuration_records(value)
        if value["publication"]["status"] in ("PENDING", "HISTORICAL_HELD"):
            self.write(
                "Current prerequisite details are withheld while publication is pending or historical. Original retained records remain diagnostic history; do not replay collection."
            )
        elif value["prerequisites"] is None:
            self.write(
                "No stage 1–4 prerequisite report has been collected. Required intake is not a completed measurement or accepted checkbox."
            )
        else:
            self.show_physical_prerequisites(value["prerequisites"])
        self.write(
            "Status uses cached projections only, without M1 reads. Initialize, refresh and collect requirements are separate explicit actions. Their storage/file effects never authorize device activation, arm power, motion or contact."
        )

    def show_physical_prerequisites(self, value: dict[str, Any]) -> None:
        # Called only after exact setup validation; no file or M1 reads here.
        self.write("Stage 1–4 requirements — NOT ASSESSED")
        self.write(
            {
                "evidence_sha256": value["evidence_sha256"],
                "power_state": "UNKNOWN",
                "epoch_observations": "8 UNMEASURED",
                "intake_observations": "17 NOT OBSERVED",
            }
        )
        self.write(value["meaning"])
        self.write(
            "DISCONNECTED_REQUIRED is a requirement, not an observed power state. Retaining these questions can move stage 1 to WAITING_OPERATOR but cannot assess, review or pass it. A stage's evidence-reference count is not the full retained inventory and does not prove checklist review."
        )
        self.write({"fixed_source_references": value["source_files"]})
        for stage in value["stages"]:
            self.write(
                {key: item for key, item in stage.items() if key != "intake_rows"}
            )
            for row in stage["intake_rows"]:
                self.write(
                    row["record_id"]
                    + ": "
                    + row["measurement"]
                    + " — OBSERVATION UNKNOWN"
                )
                self.write(
                    {
                        **{
                            key: row[key]
                            for key in (
                                "assembly",
                                "unit",
                                "template_phase",
                                "template_status",
                                "template_notes",
                                "required_observation_fields",
                            )
                        },
                        "candidate_or_requirement_NOT_OBSERVED": row[
                            "candidate_or_requirement"
                        ],
                    }
                )
                self.write(
                    "INT-005: measurement and evidence are required now. Acceptance is DEFERRED to noncontact_acceptance until TARGET_ACCURACY_BUDGET_CLOSED; collecting or measuring flatness does not accept its limit."
                    if row["record_id"] == "INT-005"
                    else "NOT ASSESSED: observed value, method, time, operator, evidence references and uncertainty are still required."
                )
                self.write(row["acceptance"])
        self.write("Five open blocking hazards — required controls and evidence")
        for hazard in value["hazards"]:
            self.write(
                hazard["id"]
                + ": "
                + hazard["title"]
                + " — OPEN BLOCKING; received-hardware evidence unassessed"
            )
            for control in hazard["controls"]:
                self.write("Required control: " + control)
            for evidence in hazard["required_evidence"]:
                self.write("Required evidence: " + evidence)
            self.write(
                {
                    key: hazard[key]
                    for key in ("fail_safe", "evidence_stages", "invalidation_epochs")
                }
            )
        self.write("Eight configuration dependencies — all UNMEASURED")
        for epoch in value["epochs"]:
            self.write({key: item for key, item in epoch.items() if key != "value"})
        if value["metadata_selection"]:
            self.write("Retained metadata context — not a received-unit measurement")
            self.write(value["metadata_selection"])
        if value["source_preflight"]:
            self.write("Separate source-only report — not stage acceptance")
            self.write(value["source_preflight"])
        self.write({"remaining_requirements": value["missing_requirements"]})

    def show_camera_fault(self, projection: Any) -> None:
        self.write("Retained camera fault explanation")
        value = _camera_fault(projection)
        if value is None:
            self.write(
                "CAMERA_FAULT_NOT_VERIFIED: Malformed diagnostic projection withheld. Inspect retained diagnostics; no retry is inferred."
            )
            return
        self.write(
            {
                key: value[key]
                for key in (
                    "status",
                    "reason_category",
                    "reported_code",
                    "basis",
                    "evidence_sha256",
                )
            }
        )
        self.write(value["reason"])
        self.write("Next investigation: " + value["next_investigation"])
        self.write(value["meaning"])
        self.write(
            "Historical retained explanation, not a current observation or authorization. No automatic retry, same-attempt replay or quarantine clearing. A reported settings rejection does not establish observed control values."
        )

    def show_camera_runtime_review(
        self, projection: Any, source: str, launch: str | None
    ) -> None:
        self.write("Runtime pair file inspection and review")
        self.write("NOT_CONNECTED / NOT_QUALIFIED / DISPATCH_DISABLED")
        self.write(
            "File agreement is not runtime admission. No executable was launched and no camera or driver was qualified by this inspection. Probe/capture, power and motion remain held."
        )
        if projection is None:
            self.write(
                "No runtime-pair inspection retained. Use the explicit file-inspection action; viewing never reads or rechecks runtime files."
            )
            return
        value = _PhysicalCameraRuntimeDisplay.projection(projection, source, launch)
        if value is None:
            self.write(
                "RUNTIME_INSPECTION_NOT_VERIFIED: Inconsistent cached inspection/review withheld. Inspect diagnostics; no file agreement or review is inferred."
            )
            return
        self.write(
            f"Status: {value['status']}; publication: {value['publication']['status']}"
        )
        self.write(value["meaning"])
        if value["publication"]["status"] == "PENDING":
            self.write(
                "Inspection/review publication pending. Details are withheld until successful result retention and completion logging."
            )
            return
        if value["publication"]["status"] == "HISTORICAL_HELD":
            self.write(
                "Historical file observations and review only; not current installed-file agreement. Original source and launch remain attached. No automatic reinspection or restoration of authority."
            )
        observed = value["inspection"]
        if observed is None:
            self.write("No runtime-pair inspection retained.")
            return
        self.write(f"Inspector: {observed['operator_id']}")
        self.write(f"Report: {observed['report_sha256']}")
        self.write(
            f"Observed source: {observed['source_sha256']}; original launch: {observed['launch_session_id']}"
        )
        coverage = observed["coverage"]
        self.write(
            f"File result: {observed['status']}; fixed paths planned {coverage['planned_paths']}, observed {coverage['observed_paths']}, unobserved {coverage['unobserved_paths']}"
        )
        for purpose in ("probe", "capture"):
            row = observed["purposes"][purpose]
            self.write(purpose + " file observations")
            self.write(
                f"{purpose}: executable pin {row['binary_status']}; build-record pin {row['build_status']}"
            )
            self.write(
                f"{purpose}: source closure {row['source_status']}; declared artifacts {row['artifact_status']}"
            )
            for kind in ("source", "artifact"):
                counts = row[kind + "_counts"]
                self.write(
                    f"{kind} rows: total {counts['total']}, matched {counts['matched']}, gaps {counts['gaps']}, unverified {counts['unverified']}"
                )
            for gap in row["gaps"]:
                self.write(f"{gap['relative_path']}: {gap['reason']}")
            if not row["gaps"]:
                self.write(
                    "No per-file gaps reported; a global inspection hold may still apply."
                )
        if value["review"] is not None:
            review = value["review"]
            self.write("Review of exact retained file report")
            self.write(f"Reviewer: {review['reviewer_id']}; {review['status']}")
            self.write(
                f"Reviewed report: {review['inspection_sha256']}; review operation: {review['review_operation_id']}"
            )
        else:
            self.write("No review recorded. Inspection never acknowledges itself.")
        self.write(
            "Labels record procedure, not authenticated independent people. Review cannot upgrade a held report. Full evidence belongs in the assigned export; this page never rebuilds, learns pins or re-inspects files."
        )

    def show_physical_camera(
        self, projection: Any, *, launch: str | None = None
    ) -> None:
        self.write("Physical camera acquisition: NOT_CONNECTED / NOT_QUALIFIED")
        self.write(
            "Metadata review is not runtime admission. Probe and capture require separate qualified runtimes and explicit server-side approval. Storage qualification is not physical authority; this panel cannot release a camera or energize the arm."
        )
        value = _PhysicalCameraDisplay.physical(projection)
        if value is None:
            self.write(
                "No physical camera plan retained. Viewing performs no device query or activation."
                if projection is None
                else "PHYSICAL_CAMERA_NOT_VERIFIED: Inconsistent or unsupported projection withheld. Inspect diagnostics; no connection or settings are inferred."
            )
            return
        self.write(
            {
                key: value[key]
                for key in ("status", "source_sha256", "session_id", "publication")
            }
        )
        self.write(value["meaning"])
        self.write(
            "CURRENT publication describes the retained plan/report. A captured-frame claim additionally requires the separately verified last-frame record below; neither means connected or qualified. Runtime candidate hashes are fixed development references, not current-file inspection or runtime approval."
        )
        if value["reviewed_endpoint"]:
            self.write(
                "Reviewed endpoint metadata — not a received-model qualification"
            )
            self.write(value["reviewed_endpoint"])
        else:
            self.write(
                "No exact reviewed endpoint retained. Never select by friendly name, camera index or raw endpoint path."
            )
        for purpose, runtime in value["runtimes"].items():
            self.write(purpose + " runtime")
            self.write(
                runtime
                if runtime
                else "Purpose-specific runtime not registered. The metadata helper does not supply this qualification."
            )
        self.show_camera_runtime_review(
            value.get("runtime_inspection"), value["source_sha256"], launch
        )
        if value["plan"]:
            self.write("Prepared plan — NOT ADMITTED")
            self.write(value["plan"])
        if value["blockers"]:
            self.write({"current_physical_gate_holds": value["blockers"]})
        self.write(
            "Reported support, intent and readback remain unqualified. No mode or electronic setting is selected automatically. Manual lens focus and aperture require physical adjustment and verification."
        )
        caps, config, observed = (
            value["configuration"][key]
            for key in ("capabilities", "candidate", "readback")
        )
        if caps:
            self.write(
                {
                    "capabilities_sha256": caps["capabilities_sha256"],
                    "probe_evidence_sha256": caps["binding"]["probe_evidence_sha256"],
                    "reported_modes": len(caps["modes"]),
                }
            )
            self.write(caps["meaning"])
            for row in caps["modes"]:
                self.write(
                    {
                        **row,
                        "display_meaning": (
                            "SUPPORTED_LAYOUT_ONLY_NOT_SELECTED"
                            if row["selectable"]
                            else "HELD"
                        ),
                    }
                )
            for control in caps["controls"]:
                self.write(
                    {
                        "reported_control": control,
                        "current_mode_meaning": (
                            "AMBIGUOUS_NO_MODE_INFERRED"
                            if control["flags"] == 3
                            else "REPORTED_NOT_APPLIED"
                        ),
                    }
                )
            self.write({"unavailable_controls": caps["unavailable_controls"]})
        else:
            self.write("No retained native capability observation.")
        if config:
            self.write("Immutable settings intent — NOT APPLIED")
            self.write(config["meaning"])
            self.write(
                {
                    key: config[key]
                    for key in (
                        "settings_epoch",
                        "mode_choice_id",
                        "mode",
                        "controls",
                        "applied",
                    )
                }
            )
        if observed:
            self.write("Retained settings readback — not pixel or power proof")
            self.write(observed["meaning"])
            self.write(
                {
                    key: observed[key]
                    for key in (
                        "status",
                        "readback_sha256",
                        "mode_matched",
                        "process_status",
                        "process_cleanup_confirmed",
                        "native_cleanup_confirmed",
                        "frame_content_verified",
                        "final_power_state",
                        "requested_mode",
                        "observed_mode",
                    )
                }
            )
            for row in observed["controls"]:
                self.write(
                    {
                        **row,
                        "display_meaning": (
                            "MATCHED_STILL_UNQUALIFIED" if row["matched"] else "HELD"
                        ),
                    }
                )
            self.write({"readback_holds": observed["reasons"]})
        self.write("Last captured frame — NOT LIVE")
        if value["status"] == "CONTENT_VERIFIED":
            self.write(
                "CONTENT_VERIFIED: retained pixel bytes and the derived still preview were verified separately from settings readback. This is not a live feed, received-model qualification or canonical stage acceptance."
            )
        frame = value["last_frame"]
        if frame:
            self.write({key: item for key, item in frame.items() if key != "image_id"})
            self.write(
                "Published cached preview from separately verified retained native pixels. A still frame is not a live connection or calibration acceptance."
                if frame["image_id"]
                else "Historical frame references only; current image publication is withheld. No automatic recapture."
            )
        else:
            self.write(
                "No separately verified physical frame has been published. Readback alone never creates an image."
            )
        if value["fault"]:
            self.show_camera_fault(value["fault"])
        self.write(
            "Viewing is device-inert. Explicit preparation may read current source files, but cannot open a device. Use only eligible preview/execute actions; no automatic retries, reconnects or arm power actions."
        )

    def show_camera_configuration(self, projection: Any) -> None:
        self.write(
            "Modeled camera capabilities and configuration: NOT_CONNECTED / NOT_QUALIFIED"
        )
        self.write(
            "These modes, ranges and readbacks are modeled incapable-fixture observations, not measured support from the purchased camera. Lens focus and aperture are manual physical adjustments; this interface cannot set or verify them."
        )
        value = _CameraConfigurationDisplay.configuration(projection)
        if value is None:
            self.write(
                "CAMERA_CONFIGURATION_NOT_VERIFIED: The cached configuration projection is missing, inconsistent or exceeds display bounds. Raw fields are withheld. Inspect retained diagnostics; do not guess support, apply defaults or replay a probe/capture."
            )
            return
        self.write({"status": value["status"], "meaning": value["meaning"]})
        self.write("Retained capability probe")
        probe = value["probe"]
        self.write(
            {
                "status": probe["status"],
                "evidence_sha256": probe["evidence_sha256"],
                **probe["binding"],
            }
        )
        if probe["process"] is not None:
            self.write("Probe: actual child process")
            self.write(probe["process"])
        if probe["native"] is not None:
            self.write("Probe: synthetic native observation")
            self.write(probe["native"])
        if probe["blockers"]:
            self.write({"probe_holds": probe["blockers"]})
        self.write(
            "A complete probe is not a complete capture. Its source lifecycle has zero control writes, samples and frames. OS process cleanup does not prove physical camera cleanup."
        )
        caps = value["capabilities"]
        if caps is None:
            self.write(
                "CAPABILITIES_UNAVAILABLE: No reported modes or control limits are inferred from an incomplete probe."
            )
        else:
            self.write(
                {
                    key: caps[key]
                    for key in (
                        "capabilities_sha256",
                        "probe_evidence_sha256",
                        "endpoint_sha256",
                    )
                }
            )
            self.write("Every reported mode; no automatic selection")
            for item in caps["modes"]:
                self.write(
                    {
                        "choice_id": item["choice_id"],
                        "mode": {
                            **item["mode"],
                            "stride_bytes": (
                                item["mode"]["stride_bytes"]
                                if item["mode"]["stride_bytes"] is not None
                                else "NOT_REPORTED"
                            ),
                        },
                        "status": (
                            "REPORTED_FORMAT_CONTRACT_ONLY"
                            if item["selectable"]
                            else "REPORTED_MODE_CAPTURE_HELD"
                        ),
                        "blockers": item["blockers"],
                    }
                )
            if not caps["modes"]:
                self.write("NO_REPORTED_MODES")
            self.write(
                "The finite fixture action can further restrict eligible modes. Its explicit mode field is the available selection list; a reported format is not a promise of capture support or physical camera compatibility."
            )
            self.write("Six electronic controls: modeled reports, not hardware limits")
            for control_id in _CameraConfigurationDisplay.IDS:
                self.write(control_id.replace("_", " "))
                item = next(
                    (
                        row
                        for row in caps["controls"]
                        if row["control_id"] == control_id
                    ),
                    None,
                )
                if item is None:
                    self.write("UNAVAILABLE_NOT_REPORTED")
                else:
                    self.write(
                        {
                            "inclusive_range": f"{item['minimum']} to {item['maximum']}",
                            "step": item["step"],
                            "reported_default_not_applied": item["default"],
                            "unit": item["unit"],
                            "capability_flags": item["capability_flags"],
                            "supported_modes": {
                                1: "AUTO",
                                2: "MANUAL",
                                3: "AUTO_AND_MANUAL_SUPPORTED",
                            }[item["capability_flags"]],
                            "current_modeled_readback": item["value"],
                            "current_flags": item["flags"],
                            "current_mode": {
                                1: "AUTO",
                                2: "MANUAL",
                                3: "AMBIGUOUS_AUTO_AND_MANUAL",
                            }[item["flags"]],
                        }
                    )
            self.write(
                "Reported defaults are informational and never automatically applied. Unreported controls have no inferred range. Current flags 3 are ambiguous, not a confirmed active mode."
            )
        self.write("Immutable candidate: staged, not applied")
        candidate = value["candidate"]
        if candidate is None:
            self.write("NO_CONFIGURATION_CANDIDATE")
        else:
            self.write(
                {
                    "settings_epoch": candidate["settings_epoch"],
                    "mode_choice_id": candidate["mode_choice_id"],
                    "mode": candidate["mode"],
                    "requested_controls": candidate["controls"],
                    "applied": False,
                }
            )
            self.write(
                "Staging does no control write. A later explicit finite campaign uses this exact candidate; changing it is not an in-stream update."
            )
        self.write("Requested versus observed modeled readback")
        observed = value["readback"]
        if observed is None:
            self.write("READBACK_NOT_AVAILABLE")
        else:
            self.write(
                {
                    key: observed[key]
                    for key in (
                        "status",
                        "settings_epoch",
                        "native_receipt_sha256",
                        "requested_mode",
                        "observed_mode",
                        "mode_matched",
                    )
                }
            )
            for row in observed["controls"]:
                self.write(
                    {
                        "control_id": row["control_id"],
                        "requested_value": row["requested"]["value"],
                        "requested_mode": row["requested"]["mode"],
                        "observed": (
                            row["observed"]
                            if row["observed"] is not None
                            else "NOT_OBSERVED"
                        ),
                        "matched": row["matched"],
                        "reasons": row["reasons"],
                    }
                )
            if observed["reasons"]:
                self.write({"readback_holds": observed["reasons"]})
        self.write(
            "Manual readback must match the requested value exactly. Auto requires an observed auto flag, not a fixed-value promise. Readback comparison does not authenticate capture provenance or qualify a received camera. No provider call, path, endpoint command or control write originates from this display."
        )

    def show_arm_resolution(self, owner: dict[str, Any]) -> None:
        self.write("Controller metadata checks before open and before write")
        if owner["schema"] == "rocell.arm_owned_evidence_summary.v1":
            self.write(
                "NOT_RETAINED — historical record format contains no two-boundary resolution trace. Do not infer these checks ran or replay the attempt to fill the gap."
            )
            return
        value = owner["resolution"]
        if value is None:
            self.write(
                "NOT_RETAINED — current-format result has no verified resolution trace. Missing trace is not a metadata match; inspect retained diagnostics without replay."
            )
            return
        self.write(
            "SYNTHETIC ONLY: fresh fixture acquisitions test the resolver, not a received controller or Windows device identity."
            if value["origin"] == "SYNTHETIC_REHEARSAL"
            else "PHYSICAL BACKEND HELD: retained metadata context does not qualify a controller or authorize connection."
        )
        self.write(f"Trace status: {value['status']}")
        self.write(f"trace_sha256: {value['trace_sha256']}")
        self.write(f"reviewed_binding_sha256: {value['reviewed_binding_sha256']}")
        for phase, label in (
            ("PRE_OPEN", "PRE_OPEN — before serial open"),
            ("PRE_WRITE", "PRE_WRITE — before the one feedback request"),
        ):
            self.write(label)
            row = next(
                (item for item in value["attempts"] if item["phase"] == phase), None
            )
            if row is None:
                self.write("NOT_ATTEMPTED: no boundary attempt is retained.")
                continue
            self.write(
                "Acquisition snapshot: "
                + ("RETAINED" if row["snapshot_sha256"] else "NOT_RETAINED")
            )
            self.write(
                "Metadata comparison report: "
                + ("RETAINED" if row["resolution_sha256"] else "NOT_RETAINED")
            )
            self.write(f"Boundary result: {row['status']}")
            for key in ("snapshot_sha256", "resolution_sha256"):
                if row[key]:
                    self.write(f"{key}: {row[key]}")
            if row["error_code"]:
                self.write(f"Retained refusal: {row['error_code']}")
        self.write(
            "A retained hash identifies evidence, not an independent successful acquisition or match. Separate checks do not establish atomic COM-to-handle identity, USB serial-descriptor identity, model, firmware, boot or power. Physical backend and release remain held."
        )

    def show_arm_process(self, projection: Any) -> None:
        self.write("Contained arm-feedback rehearsal: NOT_CONNECTED / NOT_QUALIFIED")
        self.write(
            "The child is an actual owned process; serial behavior uses a sealed incapable Win32 model, not a physical controller. Received identity, firmware and power remain unverified."
        )
        value = _arm_process(projection)
        if value is None:
            self.write(
                "ARM_PROCESS_NOT_VERIFIED: The cached summary is missing, inconsistent or exceeds display bounds. Inspect diagnostics; do not infer completion or replay."
            )
            return
        self.write(
            {
                k: v
                for k, v in value.items()
                if k
                not in {
                    "process",
                    "handshake",
                    "feedback",
                    "native",
                    "resolution",
                    "meaning",
                }
            }
        )
        self.write(value["meaning"])
        self.write(
            "Complete evidence means records were retained, not that feedback, cleanup or a physical power state passed."
        )
        for label, key in (
            ("Actual child-process containment and cleanup", "process"),
            ("Retained admission records — not proof RELEASE was sent", "handshake"),
            ("Modeled serial feedback validity", "feedback"),
            ("Modeled non-purging native-owner cleanup", "native"),
        ):
            self.write(label)
            self.write(value[key] if value[key] is not None else "EVIDENCE_MISSING")
            if key == "handshake":
                self.show_arm_resolution(value)
        self.write(
            "Release retained means planned/retained bytes. A final authorization denial can prevent sending them; inspect stdin byte counts and the verified child result separately."
        )
        self.write(
            "Process tree exit, native handle cleanup and serial close are separate. None proves physical de-energization. The worker final power remains UNKNOWN_REQUIRES_SEPARATE_OBSERVATION; inspect the independent synthetic observer in the stage assessment."
        )
        self.write(
            "Only counts and hashes are displayed. Raw serial and child bytes stay in private retained evidence. No automatic restart, replay, fallback, discovery or command follows from this card."
        )

    def show_camera_process(self, projection: Any) -> None:
        self.write("Contained camera-process rehearsal: NOT_CONNECTED / NOT_QUALIFIED")
        self.write(
            "All pixels are source-derived incapable fixtures, not physical camera frames. Process exit is not physical device cleanup. No received camera, driver, USB3 link or capture backend is qualified."
        )
        value = _camera_process(projection)
        if value is None:
            self.write(
                "CAMERA_PROCESS_NOT_VERIFIED: The cached process summary is missing, inconsistent or exceeds display bounds. Inspect diagnostics; do not infer completion or replay the campaign."
            )
            return
        self.write(
            {
                "status": value["status"],
                "evidence_sha256": value["evidence_sha256"],
                **value["binding"],
            }
        )
        self.write(value["meaning"])
        self.write("Actual child-process containment and cleanup")
        self.write(
            value["process"]
            if value["process"] is not None
            else "PROCESS_EVIDENCE_MISSING"
        )
        self.write(
            "Created, resumed and tree-exit-confirmed describe the owned OS process only. Byte counters are retained output lengths; no child output, commands or raw paths are shown."
        )
        self.write("Synthetic native receipt and cleanup")
        if value["native"] is None:
            self.write("SYNTHETIC_NATIVE_RECEIPT_MISSING")
        else:
            self.write("SYNTHETIC_ONLY_NOT_DEVICE_CLEANUP")
            self.write(value["native"])
            self.write(
                "Native counters and cleanup describe the incapable fixture contract only. An OK receipt cannot override a failed, cancelled or timed-out process."
            )
        self.write("Retained frame metadata references")
        self.write(
            value["capture"]
            if value["capture"] is not None
            else "CAPTURE_METADATA_MISSING"
        )
        self.write(
            "Metadata binding is not file-content verification. Reopening requires the backend's separate retained-content verification. This card does not load a preview; use the Camera page's current image provenance separately."
        )
        if value["blockers"]:
            self.write({"retained_campaign_holds": value["blockers"]})
        self.write(
            {
                "device_cleanup_proven": False,
                "physical_authority": False,
                "qualified": False,
            }
        )
        self.write(
            "No automatic discovery, replay, process restart or new camera action follows from this display. Use an eligible explicit action preview and exact confirmation only."
        )

    def show_retained_arm_checks(
        self,
        projection: Any,
        title: str,
        stages: tuple[str, ...],
        limitations: str,
        *,
        show_observed: bool = True,
    ) -> None:
        """Presentation only: never interpret fault success as nominal readiness."""
        self.write(title)
        self.write(limitations)

        def digest(value: Any) -> bool:
            return (
                type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None
            )

        def short_text(value: Any) -> bool:
            return type(value) is str and 0 < len(value) <= 512

        record = type(projection) is dict
        provenance = (
            _compact_check_data(projection["provenance"])
            if record and type(projection.get("provenance")) is dict
            else None
        )
        valid = (
            record
            and projection.get("stage") in stages
            and projection.get("outcome") in ("REHEARSAL_CHECKS_PASSED", "BLOCKED")
            and projection.get("physical_authority") is False
            and short_text(projection.get("meaning"))
            and digest(projection.get("evaluation_sha256"))
            and digest(projection.get("selected_inputs_sha256"))
            and provenance is not None
            and type(projection.get("checks")) is list
            and 0 < len(projection["checks"]) <= 16
        )
        if not valid:
            self.write(
                "NOT_VERIFIED: The retained check projection is missing, inconsistent or exceeds display bounds. Inspect diagnostics; no passing result is inferred and no report is silently truncated."
            )
            return
        self.write(
            {
                "evaluated_stage": projection["stage"],
                "reported_outcome": projection["outcome"],
                "evaluation_sha256": projection["evaluation_sha256"],
                "selected_inputs_sha256": projection["selected_inputs_sha256"],
                "physical_authority": False,
            }
        )
        self.write(projection["meaning"])
        if show_observed:
            self.write("Synthetic input provenance:")
            self.write(provenance)
        for check in projection["checks"]:
            row = type(check) is dict
            kind = (
                check.get("check_kind")
                if row
                and check.get("check_kind")
                in ("NOMINAL", "EXPECTED_FAULT", "INVARIANT")
                else "UNKNOWN_CHECK_KIND"
            )
            observed = _compact_check_data(check.get("observed")) if row else None
            valid_row = (
                row
                and type(check.get("check_id")) is str
                and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", check["check_id"])
                is not None
                and kind != "UNKNOWN_CHECK_KIND"
                and type(check.get("passed")) is bool
                and short_text(check.get("meaning"))
                and "observed" in check
                and observed is not None
            )
            status = (
                "NOT_VERIFIED"
                if not valid_row
                else (
                    "BLOCKED"
                    if not check["passed"]
                    else kind + "_CHECK_PASSED_REHEARSAL"
                )
            )
            self.write(
                {
                    "check": (
                        check["check_id"] if valid_row else "Invalid retained check"
                    ),
                    "check_kind": kind,
                    "check_status": status,
                }
            )
            if valid_row:
                self.write(check["meaning"])
                if show_observed:
                    self.write("Observed check data:")
                    self.write(observed)
            else:
                self.write(
                    "Check data is not verified for display. Inspect its retained report; do not infer a passing result."
                )
        self.write(
            "Expected-fault checks verify expected handling only; they cannot replace passing nominal checks. This view does not assess, review, replay, or advance a stage. The separate rehearsal journal and exact review remain authoritative."
        )

    def show_retained_feedback(self, projection: Any) -> None:
        """Keep serial response, cleanup and independent power evidence distinct."""
        self.show_retained_arm_checks(
            projection,
            "Retained synthetic feedback campaign",
            ("feedback_only_connection",),
            "Simulation only: no physical serial port, arm connection, firmware qualification or energy observation. A valid response does not establish pose, stationarity or safe power-off.",
            show_observed=False,
        )

        def digest(value: Any) -> bool:
            return (
                type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None
            )

        def count(value: Any) -> bool:
            return type(value) is int and 0 <= value <= 9_007_199_254_740_991

        def identifier(value: Any) -> bool:
            return type(value) is str and _IDENTIFIER.fullmatch(value) is not None

        def error(value: Any) -> bool:
            return value is None or (
                type(value) is dict
                and set(value) == {"code", "phase", "error_type"}
                and all(identifier(item) for item in value.values())
            )

        summary = projection.get("safe_summary") if type(projection) is dict else None
        count_keys = (
            "object_creations",
            "identity_checks",
            "open_attempts",
            "opens_confirmed",
            "unexpected_open_objects",
            "write_attempts",
            "writes_confirmed",
            "write_bytes_confirmed",
            "read_attempts",
            "read_bytes_retained",
            "close_attempts",
            "closes_confirmed",
        )
        valid = (
            type(summary) is dict
            and summary.get("schema") == "rocell.rehearsal_arm_feedback_summary.v1"
            and all(
                digest(summary.get(key))
                for key in (
                    "binding_sha256",
                    "source_sha256",
                    "request_sha256",
                    "controller_binding_sha256",
                )
            )
            and summary.get("worker_outcome")
            in (
                "SUCCEEDED_DIAGNOSTIC",
                "BLOCKED_PRE_OPEN",
                "CANCELLED_PRE_OPEN",
                "FAILED_UNCERTAIN",
            )
            and all(
                type(summary.get(key)) is bool
                for key in (
                    "technical_response_valid",
                    "feedback_receipt_valid",
                    "serial_cleanup_confirmed",
                    "effect_uncertain",
                )
            )
            and summary.get("final_power_state")
            == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
            and summary.get("physical_authority") is False
            and summary.get("arm_connected") is False
            and summary.get("installed_firmware_proven_by_packet") is False
            and type(summary.get("api_counts")) is dict
            and all(count(summary["api_counts"].get(key)) for key in count_keys)
            and "primary_error" in summary
            and error(summary["primary_error"])
            and type(summary.get("cleanup_errors")) is list
            and len(summary["cleanup_errors"]) <= 8
            and all(
                item is not None and error(item) for item in summary["cleanup_errors"]
            )
            and type(summary.get("wire")) is dict
            and all(
                type(summary["wire"].get(key)) is dict
                and digest(summary["wire"][key].get("sha256"))
                and count(summary["wire"][key].get("retained_bytes"))
                for key in ("response", "unexpected")
            )
            and type(summary["wire"]["unexpected"].get("unretained_bytes")) is int
            and summary["wire"]["unexpected"]["unretained_bytes"] >= 0
            and type(summary.get("timing")) is dict
            and summary["timing"].get("basis")
            == "HOST_READ_COMPLETION_NOT_DEVICE_TIMESTAMP"
            and type(summary["timing"].get("transaction_timing_available")) is bool
            and count(summary["timing"].get("elapsed_ns"))
        )
        if not valid:
            self.write(
                "NOT_VERIFIED: Safe serial summary is missing or invalid. No response validity, serial cleanup, or worker power result is inferred. Raw evidence is never expanded here."
            )
        else:
            assert isinstance(summary, dict)  # Narrow the validated cached record.
            self.write("Technical response — separate from cleanup")
            self.write(
                "VALID_SYNTHETIC_RESPONSE"
                if summary["technical_response_valid"]
                else "RESPONSE_NOT_VALIDATED"
            )
            self.write(
                {
                    "worker_outcome": summary["worker_outcome"],
                    "complete_feedback_receipt_valid": summary[
                        "feedback_receipt_valid"
                    ],
                    "request_sha256": summary["request_sha256"],
                    "controller_binding_sha256": summary["controller_binding_sha256"],
                }
            )
            self.write(
                "Packet validity can be true even when close/cleanup failed. It proves neither installed firmware nor calibrated position."
            )
            self.write("Serial cleanup — separate from power")
            self.write(
                "SERIAL_API_CLEANUP_CONFIRMED"
                if summary["serial_cleanup_confirmed"]
                else "SERIAL_CLEANUP_NOT_CONFIRMED"
            )
            self.write({"effect_uncertain": summary["effect_uncertain"]})
            self.write(
                "Closing a simulated serial handle is not a DC disconnect, an emergency stop, or evidence that actuator power is off."
            )
            if summary["primary_error"] is not None:
                self.write({"primary_error_codes": summary["primary_error"]})
            if summary["cleanup_errors"]:
                self.write({"cleanup_error_codes": summary["cleanup_errors"]})
            self.write("Simulated serial API counters")
            self.write({key: summary["api_counts"][key] for key in count_keys})
            self.write(
                "These are incapable-backend API calls, not physical device operations. No raw request, response, boot bytes or arbitrary endpoint is displayed."
            )
            self.write("Retained wire hashes and counts")
            omitted = summary["wire"]["unexpected"]["unretained_bytes"]
            self.write(
                {
                    "response_sha256": summary["wire"]["response"]["sha256"],
                    "response_bytes_retained": summary["wire"]["response"][
                        "retained_bytes"
                    ],
                    "unexpected_sha256": summary["wire"]["unexpected"]["sha256"],
                    "unexpected_bytes_retained": summary["wire"]["unexpected"][
                        "retained_bytes"
                    ],
                    "unexpected_bytes_unretained": (
                        omitted if count(omitted) else "NOT_EXACT_IN_DISPLAY"
                    ),
                    "binding_sha256": summary["binding_sha256"],
                    "source_sha256": summary["source_sha256"],
                    "host_elapsed_ns": summary["timing"]["elapsed_ns"],
                    "timing_basis": summary["timing"]["basis"],
                    "transaction_timing_available": summary["timing"][
                        "transaction_timing_available"
                    ],
                }
            )
            self.write(
                "Absolute monotonic timestamps stay in retained evidence and are not rendered as device timestamps. Unsafe numeric values are never rounded into an exact-looking count."
            )
        # This knowledge limitation is not overwritten by an API-close result
        # or by a separate, explicitly synthetic post-campaign observer.
        self.write("Worker final-power knowledge")
        self.write("UNKNOWN_REQUIRES_SEPARATE_OBSERVATION")
        self.write(
            "The serial worker cannot observe final actuator power. Response validity and serial cleanup do not change this UNKNOWN state."
        )
        observation = (
            projection.get("final_power_observation")
            if type(projection) is dict
            else None
        )
        self.write("Independent synthetic final-power observation")
        owned_observation = (
            type(observation) is dict
            and observation.get("schema")
            == "rocell.owned_arm_synthetic_final_power_observation.v1"
        )
        observation_valid = (
            type(observation) is dict
            and observation.get("schema")
            in (
                "rocell.synthetic_final_power_observation.v1",
                "rocell.owned_arm_synthetic_final_power_observation.v1",
            )
            and observation.get("origin") == "SYNTHETIC_REHEARSAL"
            and observation.get("observation_kind")
            == "INDEPENDENT_POST_CAMPAIGN_FIXTURE"
            and identifier(observation.get("observer_id"))
            and observation.get("observed_power_state")
            in ("DEENERGIZED", "ENERGIZED", "UNKNOWN")
            and observation.get("observed_after_worker") is True
            and observation.get("physical_observation") is False
            and observation.get("serial_close_used_to_infer_power") is False
            and all(
                digest(observation.get(key))
                for key in (
                    "permit_sha256",
                    "observation_sha256",
                )
            )
            and (
                digest(observation.get("feedback_evidence_sha256"))
                or (
                    owned_observation
                    and observation.get("feedback_evidence_sha256") is None
                )
            )
            and (
                not owned_observation
                or (
                    digest(observation.get("owned_evidence_sha256"))
                    and observation.get("process_cleanup_used_to_infer_power") is False
                )
            )
        )
        if not observation_valid:
            self.write(
                "FINAL_POWER_OBSERVATION_MISSING"
                if observation is None
                else "FINAL_POWER_OBSERVATION_NOT_VERIFIED"
            )
            self.write(
                "A separate retained synthetic post-campaign observation is missing or invalid. No known final power state or replay permission is inferred."
            )
        else:
            assert isinstance(observation, dict)
            self.write(
                "SYNTHETIC_DEENERGIZED_OBSERVATION_ONLY"
                if observation["observed_power_state"] == "DEENERGIZED"
                else "FINAL_POWER_OBSERVATION_HOLD"
            )
            self.write(
                {
                    "recorded_synthetic_state": observation["observed_power_state"],
                    "observer_id": observation["observer_id"],
                    "observed_after_worker": True,
                    "permit_sha256": observation["permit_sha256"],
                    "feedback_evidence_sha256": observation["feedback_evidence_sha256"],
                    "observation_sha256": observation["observation_sha256"],
                    "physical_observation": False,
                    "serial_close_used_to_infer_power": False,
                }
            )
            if owned_observation:
                self.write(
                    {
                        "owned_evidence_sha256": observation["owned_evidence_sha256"],
                        "process_cleanup_used_to_infer_power": False,
                    }
                )
                self.write(
                    "This separate synthetic observer follows the owned campaign. Its IPC evidence hash and actual inner feedback hash are distinct; no absolute host timestamp is rendered."
                )
        self.write(
            "This independent fixture observation is rehearsal evidence only, not a measurement of real power. It does not rewrite the worker's UNKNOWN state. Missing, UNKNOWN or ENERGIZED results require the backend's explicit hold; the view cannot clear it or authorize another attempt."
        )

    def show_retained_reference(self, projection: Any) -> None:
        """Present nominal math separately from physical calibration authority."""
        self.show_retained_arm_checks(
            projection,
            "Retained synthetic reference-frame checks",
            ("reference_frame_calibration",),
            "Nominal software rehearsal only: no installed calibration, physical bootstrap/reference receipt importer, energy change, robot motion or contact. T105 feedback is not a calibrated joint state.",
        )
        pending = (
            "bootstrap_phase_receipt",
            "reference_characterization_phase_receipt",
            "arm_to_board_transform",
            "controller_model_correlation",
            "free_state_tool_tcp",
            "keyboard_target_map",
            "phone_target_map",
            "outcome_observer_candidates",
        )

        def exact(value: Any, keys: tuple[str, ...]) -> bool:
            return type(value) is dict and set(value) == set(keys)

        def count(value: Any) -> bool:
            return type(value) is int and 0 <= value <= 9_007_199_254_740_991

        def metric(value: Any) -> bool:
            return value is None or (
                type(value) in (int, float)
                and math.isfinite(value)
                and 0 <= value <= 9_007_199_254_740_991
            )

        def coverage(value: Any) -> bool:
            return (
                exact(value, ("selected", "catalog_total"))
                and count(value["catalog_total"])
                and type(value["selected"]) is list
                and len(value["selected"]) == 1
                and value["catalog_total"] > len(value["selected"])
                and all(
                    type(item) is str
                    and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", item) is not None
                    for item in value["selected"]
                )
            )

        summary = (
            projection.get("reference_summary") if type(projection) is dict else None
        )
        valid = (
            isinstance(summary, dict)
            and exact(
                summary,
                (
                    "schema",
                    "graph",
                    "numeric",
                    "target_coverage",
                    "claim",
                    "physical_components_pending",
                    "camera_role",
                    "controller_feedback_role",
                ),
            )
            and summary["schema"] == "rocell.rehearsal_reference_summary.v1"
            and exact(
                summary["graph"],
                (
                    "nominal_artifacts",
                    "parent_edges",
                    "context_edges",
                    "detected_edges",
                ),
            )
            and all(
                count(summary["graph"][key])
                for key in (
                    "nominal_artifacts",
                    "parent_edges",
                    "context_edges",
                    "detected_edges",
                )
            )
            and summary["graph"]["nominal_artifacts"] == 15
            and summary["graph"]["parent_edges"] == 27
            and summary["graph"]["context_edges"] == 41
            and summary["graph"]["detected_edges"]
            <= summary["graph"]["parent_edges"] + summary["graph"]["context_edges"]
            and exact(
                summary["numeric"],
                (
                    "training_points",
                    "heldout_points",
                    "training_rms_mm",
                    "heldout_rms_mm",
                    "max_roundtrip_error_mm",
                ),
            )
            and type(summary["numeric"]["training_points"]) is int
            and summary["numeric"]["training_points"] == 4
            and type(summary["numeric"]["heldout_points"]) is int
            and summary["numeric"]["heldout_points"] == 2
            and all(
                metric(summary["numeric"][key])
                for key in (
                    "training_rms_mm",
                    "heldout_rms_mm",
                    "max_roundtrip_error_mm",
                )
            )
            and exact(summary["target_coverage"], ("keyboard", "phone"))
            and coverage(summary["target_coverage"]["keyboard"])
            and coverage(summary["target_coverage"]["phone"])
            and summary["target_coverage"]["keyboard"]["catalog_total"] == 46
            and summary["target_coverage"]["phone"]["catalog_total"] == 29
            and summary["claim"]
            == "TWO_TARGET_COORDINATE_ROUNDTRIPS_NOT_REACHABILITY_OR_COMPLETE_COVERAGE"
            and type(summary["physical_components_pending"]) is list
            and len(summary["physical_components_pending"]) == len(pending)
            and all(
                type(item) is str for item in summary["physical_components_pending"]
            )
            and set(summary["physical_components_pending"]) == set(pending)
            and summary["camera_role"] == "DEPENDENCY_ONLY_NOT_NUMERIC_INPUT"
            and summary["controller_feedback_role"]
            == "TRANSPORT_ONLY_NOT_CALIBRATED_JOINT_INPUT"
        )
        if not valid:
            self.write(
                "NOT_VERIFIED: Reference summary is missing, inconsistent or exceeds display bounds. No zero residual, complete coverage or installed calibration is inferred; inspect the retained report."
            )
        else:
            assert isinstance(summary, dict)
            self.write("Nominal graph and injected-staleness coverage")
            self.write(summary["graph"])
            self.write(
                "The 15 nominal artifacts are dependency fixtures. Detected stale edges describe deliberately injected failures, not measured calibration quality or physical closure."
            )
            self.write("Synthetic point fit and coordinate roundtrips")
            self.write(
                {
                    key: value if value is not None else "NOT_AVAILABLE"
                    for key, value in summary["numeric"].items()
                }
            )
            self.write(
                "Residuals use synthetic points and nominal FK/frame inputs. Small errors do not measure installed geometry, controller correlation, TCP or real targeting accuracy."
            )
            self.write("Explicit target subset")
            for device in ("keyboard", "phone"):
                entry = summary["target_coverage"][device]
                self.write(
                    {
                        "device": device,
                        "selected_targets": ", ".join(entry["selected"]),
                        "selected_count": len(entry["selected"]),
                        "catalog_total": entry["catalog_total"],
                    }
                )
            self.write(
                "Only two target coordinate roundtrips are represented: not all 75 keyboard/phone targets, no IK reachability, no route or collision qualification, and no physical typing/tapping acceptance."
            )
        # Always show the physical holds, even when a malformed input claims a
        # successful component status. This view cannot qualify a component.
        self.write("Eight physical reference components remain pending")
        for name in pending:
            self.write({"component": name, "physical_status": "PENDING"})
        self.write(
            "Camera stages 6, 7 and 8 are DEPENDENCY_ONLY_NOT_NUMERIC_INPUT. Controller feedback is TRANSPORT_ONLY_NOT_CALIBRATED_JOINT_INPUT: transport validity does not turn T105 fields into calibrated joints."
        )
        self.write(
            "Use the existing explicit collect, assess and exact review steps. No bootstrap importer or physical calibration control is provided here. Noncontact acceptance requires its own exact assessment; this reference rehearsal cannot accept it. Contact-dependent graph nodes are future requirements, not a physical closure granted by this rehearsal."
        )

    def show_retained_noncontact(self, projection: Any) -> None:
        """Keep real gaps separate from finite synthetic calculator controls."""
        title = "Retained noncontact readiness gaps"
        limitations = "No power, movement or contact is authorized. This is a no-device readiness report, not a move button, physical acceptance or stage-15 handoff."
        value = _noncontact_projection(projection)
        if value is None:
            self.write(title)
            self.write(limitations)
            self.write(
                "NOT_VERIFIED: Noncontact projection is missing, inconsistent or exceeds display bounds. Readiness remains held; no partial passing checks or raw technical reports are displayed."
            )
            return
        self.show_retained_arm_checks(
            value, title, ("noncontact_acceptance",), limitations
        )
        s = value["safe_summary"]
        h, g, a = (
            s[key] for key in ("collision_historical", "static_geometry", "accuracy")
        )
        self.write("Nominal build readiness: BLOCKED")
        self.write(
            "Successful synthetic fault/control checks cannot close missing installed geometry or unmeasured accuracy. A review records the blockage; it cannot advance to handoff."
        )
        self.write("Historical collision audit — eye-on-arm only")
        self.write(h)
        self.write(
            "The historical 19-body audit and nominal AABB proxies are not the updated static B0477 geometry or installed clearance."
        )
        self.write("Separate static-camera geometry requirements")
        self.write(g)
        self.write(
            "All 26 static body requirements and nine source identities need their own complete geometry contract. Retained source-design hashes are not installed geometry; the missing-source list is separate from the required-source count. Names do not create measured shapes; pose and sweep clearance were not evaluated."
        )
        self.write("Real-build accuracy — UNBOUNDED")
        self.write(
            {
                key: ("NOT_AVAILABLE" if item is None else item)
                for key, item in a.items()
                if key != "controls"
            }
        )
        self.write(
            {
                key: ("NOT_AVAILABLE" if item is None else item)
                for key, item in a["controls"][0].items()
            }
        )
        self.write(
            "Missing bounds are NOT_AVAILABLE, never zero. The real_unmeasured calculation uses a synthetic target boundary to expose missing measurements; no target-specific safe geometry or measured accuracy is qualified."
        )
        self.write("Separate synthetic accuracy controls")
        self.write(
            "These fixed typed calculator cases use synthetic inputs, not the installed keyboard or phone. Finite sums and signed margins belong only to those controls; a finite control does not bound the real build."
        )
        for row in a["controls"][1:]:
            self.write(
                {
                    key: ("NOT_AVAILABLE" if item is None else item)
                    for key, item in row.items()
                }
            )
        self.write("Actual selected nominal domain and tool")
        self.write(s["selection"])
        self.write(
            "No target reachability was evaluated: 0 of 46 keyboard targets and 0 of 29 phone targets. No passing UNMEASURED_SENSITIVITY_OVERLAY was substituted for this nominal selection."
        )
        self.write("Original reviewed stage-13 dependencies")
        self.write(s["dependencies"])
        self.write(
            "Exact reviewed dependency identities are retained, not new measurements. Camera evidence is DEPENDENCY_ONLY_NOT_NUMERIC_INPUT; controller feedback is TRANSPORT_ONLY_NOT_CALIBRATED_JOINT_INPUT. No T105 fields become calibrated joints."
        )
        self.write("Not evaluated by this report")
        for axis in s["not_evaluated"]:
            self.write({"axis": axis, "status": "NOT_EVALUATED"})
        self.write(
            "Zero actual device opens, acquired camera frames, serial writes, robot motions and contacts. No virtual route or plant ran in this slice. NC-02/NC-03 and all physical release gates remain open requirements."
        )
        self.write(
            "Use the existing explicit collect, assess and exact review steps. Export the original retained evidence for development review. Rendering, polling and export never rerun a diagnostic or accept stage 14."
        )

    def show_reopening(self, rehearsal: dict[str, Any]) -> None:
        """Display server-owned selections without discovery, opening or replay."""
        self.write("\nExisting rehearsal stores")
        self.write(
            "Discover reads only the assigned registry. Opening is a separate exact-confirmation action: "
            "it requalifies storage and acquires/releases leases on the original session. "
            "Viewing this screen does neither. No session is copied, prior operation replayed or preview loaded."
        )
        discovery = rehearsal.get("discovery")
        if not isinstance(discovery, dict):
            self.write(
                "Existing stores have not been discovered. Use the explicit Discover action."
            )
        else:
            choices = discovery.get("choices")
            if not isinstance(choices, list) or not choices:
                self.write(
                    "No store choices are displayed. Review discovery status/issues; do not enter a path."
                )
            elif len(choices) > 128:
                self.write(
                    "Discovery exceeds the display limit. Inspect diagnostics; no truncated list is presented."
                )
            else:
                for choice in choices:
                    if not isinstance(choice, dict) or not isinstance(
                        choice.get("choice_id"), str
                    ):
                        self.write(
                            "Invalid discovery record. Do not infer a store selection."
                        )
                        continue
                    self.write(
                        {
                            "existing_store": {
                                key: choice.get(key)
                                for key in (
                                    "choice_id",
                                    "directory",
                                    "cell_id",
                                    "session_id",
                                    "status",
                                    "source_matches",
                                    "session_header_sha256",
                                    "discovery_sha256",
                                )
                            }
                        }
                    )
            issues = discovery.get("issues")
            if isinstance(issues, list):
                self.write({"discovery_issues": issues[:128]})
        result = rehearsal.get("reopen_result")
        if not isinstance(result, dict):
            return
        self.write(
            {
                "last_explicit_open": {
                    key: result.get(key)
                    for key in (
                        "status",
                        "original_session_reopened",
                        "disposition",
                        "operator_id",
                    )
                }
            }
        )
        if result.get("status") == "OPENED":
            self.write(
                "Original rehearsal reopened, not copied. Active directory/cell/session:"
            )
            self.write(
                {
                    key: rehearsal.get(key)
                    for key in ("directory", "cell_id", "session_id")
                }
            )
            if rehearsal.get("stage_state") == "REVIEW_PENDING":
                self.write(
                    "Retained assessment awaits a fresh, distinct reviewer. Reopening restores evidence, not acceptance or prior approval."
                )
            if result.get("disposition") == "WAITING_NO_RECEIPT":
                self.write(
                    "At reopening, this stage was waiting without an assessable receipt. That historical result does not prove current collection or authorize replay. An unrecorded operator must be supplied explicitly."
                )
        elif result.get("status") == "READ_ONLY_HOLD":
            self.write(
                "Existing store held read-only. No restored approval or operational adapter was admitted. Inspect/export; do not repair, reset or replay."
            )
        reasons = result.get("reasons")
        if isinstance(reasons, list):
            self.write({"open_hold_reasons": reasons[:128]})

    @staticmethod
    def _field(field: Any) -> dict[str, Any]:
        if not isinstance(field, dict) or set(field) - _FIELD_KEYS:
            raise ValueError("Unrecognized action field schema; nothing was prepared.")
        name = field.get("name")
        if (
            not isinstance(name, str)
            or not _IDENTIFIER.fullmatch(name)
            or name in _RESERVED_FIELDS
        ):
            raise ValueError(
                "Raw hardware, path, command and authority fields are not accepted."
            )
        if field.get("type") not in {
            "text",
            "textarea",
            "select",
            "number",
            "checkbox",
        }:
            raise ValueError("Unsupported field type; nothing was prepared.")
        if (
            not isinstance(field.get("label"), str)
            or type(field.get("required", False)) is not bool
        ):
            raise ValueError(
                "Action field is missing its label or has an invalid requirement."
            )
        return field

    def gather(
        self, action: dict[str, Any], view: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        intake = None
        if action.get("action_id") == "physical_received_camera_draft_record":
            received = _ReceivedCameraDisplay.validate(
                (view or {}).get("received_camera_onboarding"), view or {}
            )
            if (
                received is None
                or received["schema"] != "rocell.wizard_received_camera.v1"
                or received["publication"]["status"] != "CURRENT"
                or received["draft"] is None
            ):
                raise ValueError(
                    "Current original received-camera draft questions are unavailable. Nothing was prepared."
                )
            intake = {"notebook": received["draft"]}
        if action.get("action_id") == "physical_intake_record":
            intake = _PhysicalIntakeDisplay.validate(
                (view or {}).get("physical_intake"),
                (view or {}).get("physical_camera_setup"),
            )
            if intake is None or intake["status"] != "CURRENT_DRAFT":
                raise ValueError(
                    "Current source-bound intake questions are unavailable. Nothing was prepared."
                )
        definitions = action.get("fields")
        received_submit = action.get("action_id") == "physical_received_camera_submit"
        maximum_fields = (
            len(_ReceivedCameraDisplay.SUBMIT_FIELDS) if received_submit else 24
        )
        if not isinstance(definitions, list) or len(definitions) > maximum_fields:
            raise ValueError(
                "Action has no bounded field schema; nothing was prepared."
            )
        fields = [self._field(field) for field in definitions]
        if (
            received_submit
            and tuple(field["name"] for field in fields)
            != _ReceivedCameraDisplay.SUBMIT_FIELDS
        ):
            raise ValueError(
                "Received-camera submission must use the exact bounded field roster; nothing was prepared."
            )
        if len({field["name"] for field in fields}) != len(fields):
            raise ValueError(
                "Action fields contain duplicate names; nothing was prepared."
            )
        values: dict[str, Any] = {}
        for field in fields:
            name, kind, label = field["name"], field["type"], field["label"]
            default = field.get("default")
            if field.get("help"):
                self.write(field["help"])
            options = field.get("options", [])
            if kind == "select":
                # Match the closed metadata inventory's per-device-class bound.
                if not isinstance(options, list) or not options or len(options) > 128:
                    raise ValueError(
                        "Selection has no bounded choices; nothing was prepared."
                    )
                for index, option in enumerate(options, 1):
                    if not isinstance(option, dict) or not isinstance(
                        option.get("value"), str
                    ):
                        raise ValueError(
                            "Invalid selection schema; nothing was prepared."
                        )
                    self.write(
                        f"  {index}. {option.get('label', option['value'])} [{option['value']}]"
                    )
            suffix = (
                " [yes/no; Enter means no]"
                if kind == "checkbox"
                else f" [default: {default}]" if default is not None else ""
            )
            raw = self.ask(f"{label}{suffix}: ")
            if raw.strip() == ":back":
                raise _Back()
            if kind == "checkbox":
                normalized = raw.strip().lower()
                if normalized not in {"", "yes", "no"}:
                    raise ValueError(
                        "Enter exactly yes or no; no confirmation was recorded."
                    )
                value: Any = normalized == "yes"
                if field.get("required") and not value:
                    raise ValueError(
                        "This explicit confirmation is required; nothing was prepared."
                    )
            else:
                value = default if raw == "" and default is not None else raw
                if kind == "select":
                    # An explicitly reviewed default is allowed; otherwise
                    # Enter never means the first detected device/choice.
                    if raw.isdecimal() and 1 <= int(raw) <= len(options):
                        value = options[int(raw) - 1]["value"]
                    if value not in {option["value"] for option in options}:
                        raise ValueError(
                            "Select one of the displayed choices; nothing was prepared."
                        )
                elif kind == "number":
                    if type(value) not in (int, float):
                        try:
                            value = (
                                int(value)
                                if re.fullmatch(r"[+-]?\d+", str(value))
                                else float(value)
                            )
                        except (ValueError, TypeError, OverflowError) as error:
                            raise ValueError(
                                "Enter a finite number; nothing was prepared."
                            ) from error
                    try:
                        finite = type(value) in (int, float) and math.isfinite(value)
                    except OverflowError:
                        finite = False
                    if not finite:
                        raise ValueError("Enter a finite number; nothing was prepared.")
                    if ("min" in field and value < field["min"]) or (
                        "max" in field and value > field["max"]
                    ):
                        raise ValueError(
                            "The number is outside the displayed action's range."
                        )
                elif (
                    not isinstance(value, str)
                    or (field.get("required") and not value.strip())
                    or len(value) > field.get("max_length", 256)
                ):
                    raise ValueError(
                        "Text is missing or exceeds this action's limit; nothing was prepared."
                    )
                elif any(
                    ord(character) < 32 and character not in "\n\t"
                    for character in value
                ):
                    raise ValueError(
                        "Control characters are not accepted as task input."
                    )
            values[name] = value
            if intake is not None and name == "record_id":
                question = next(
                    (
                        row
                        for row in intake["notebook"]["rows"]
                        if row["record_id"] == value
                    ),
                    None,
                )
                if question is None:
                    raise ValueError(
                        "Select an exact original notebook question; nothing was prepared."
                    )
                self.show_intake_question(question)
        return values

    def perform(self, view: dict[str, Any], action: dict[str, Any]) -> str | None:
        if action.get("enabled") is not True:
            raise ValueError("This action is held; nothing was prepared.")
        if action.get("description"):
            self.write(action["description"])
        values = self.gather(action, view)
        ticket = self.service.prepare_action(
            action["action_id"], values, view["revision"]
        )
        if (
            not isinstance(ticket, dict)
            or not isinstance(ticket.get("ticket_id"), str)
            or not _IDENTIFIER.fullmatch(ticket["ticket_id"])
        ):
            raise ValueError(
                "The service did not return a valid action ticket. Nothing was executed."
            )
        self.write(
            "\nReview the exact prepared action. Preparation has not executed it:"
        )
        self.write(ticket)
        self.write(
            "Only this ticket will be submitted. Empty input, no, or :back cancels."
        )
        if self.ask("Type yes to execute this exact action: ").strip().lower() != "yes":
            self.write("Canceled. The prepared ticket was not executed.")
            return None
        # Never resubmit a ticket after an exception or transport uncertainty.
        operation = self.service.execute_action(ticket["ticket_id"])
        self.write(operation)
        identifier = (
            operation.get("operation_id") if isinstance(operation, dict) else None
        )
        if not isinstance(identifier, str) or not _IDENTIFIER.fullmatch(identifier):
            raise ValueError(
                "No valid operation ID was returned. Inspect current operations before any retry."
            )
        return identifier

    def stop(self) -> None:
        self.write(
            "Stopping a diagnostic is not a robot emergency stop and does not prove power-off."
        )
        view = self.snapshot()
        action = next(
            (item for item in view["actions"] if item["action_id"] == "stop_operation"),
            None,
        )
        if action is None or action.get("enabled") is not True:
            self.write(
                "No registered stop action is currently eligible. Inspect existing operations; no alternate stop command was issued."
            )
            return
        try:
            identifier = self.perform(view, action)
            if identifier:
                self.write(self.service.operation(identifier))
        except _Back:
            self.write("Stop preview canceled; no stop action was executed.")

    def monitor(self, identifier: str) -> None:
        previous: Any = None
        while True:
            interrupted = False
            try:
                for _ in range(POLL_WINDOW_STEPS):
                    operation = self.service.operation(identifier)
                    if not isinstance(operation, dict):
                        raise ValueError(
                            "Invalid operation report; inspect diagnostics before retrying."
                        )
                    status = operation.get("status")
                    if status not in _TERMINAL_STATES | {"QUEUED", "RUNNING"}:
                        raise ValueError(
                            "Unknown operation state; nothing was automatically retried."
                        )
                    progress = (
                        status,
                        operation.get("progress"),
                        operation.get("message"),
                    )
                    if progress != previous:
                        self.write(
                            {
                                "operation_id": identifier,
                                "status": status,
                                "progress": operation.get("progress"),
                                "message": operation.get("message"),
                            }
                        )
                        previous = progress
                    if status in _TERMINAL_STATES:
                        result = operation.get("result")
                        steps = (
                            result.get("steps") if isinstance(result, dict) else None
                        )
                        displayed = operation
                        if (
                            isinstance(result, dict)
                            and isinstance(steps, list)
                            and len(steps) <= 32
                        ):
                            shown_steps = []
                            for step in steps:
                                if (
                                    isinstance(step, dict)
                                    and step.get("name")
                                    == "retained-incapable-owned-camera-diagnostics"
                                ):
                                    report = step.get("report")
                                    if (
                                        isinstance(report, dict)
                                        and report.get("camera_fault_diagnostic")
                                        is not None
                                    ):
                                        self.show_camera_fault(
                                            report["camera_fault_diagnostic"]
                                        )
                                    if isinstance(report, dict):
                                        step = {
                                            **step,
                                            "report": {
                                                key: item
                                                for key, item in report.items()
                                                if key != "camera_fault_diagnostic"
                                            },
                                        }
                                shown_steps.append(step)
                            displayed = {
                                **operation,
                                "result": {**result, "steps": shown_steps},
                            }
                        self.write(displayed)
                        return
                    self.sleep(POLL_INTERVAL_S)
            except KeyboardInterrupt:
                interrupted = True
                self.write(
                    "Monitoring interrupted. The existing operation was not replayed or assumed stopped."
                )
            prompt = (
                "Monitoring paused."
                if interrupted
                else "The diagnostic is still running after this bounded monitoring window."
            )
            self.write(
                prompt
                + " Enter wait to monitor again, stop to preview the registered diagnostic stop, or back to return to status."
            )
            choice = self.ask("wait / stop / back [back]: ").strip().lower()
            if choice == "wait":
                continue
            if choice == "stop":
                self.stop()
            elif choice not in {"", "back", ":back"}:
                self.write(
                    "Unknown monitoring command. Returning to status without dispatch."
                )
            return

    def run(self) -> int:
        while True:
            try:
                view = self.snapshot()
                available = self.show(view)
            except Exception as error:
                self.write(f"Cannot read a trustworthy workbench state: {error}")
                return 1
            try:
                choice = self.ask("Select action or command: ").strip()
                if choice.lower() in {"quit", "exit", "q"}:
                    self.write(
                        "Terminal closed. No action was inferred from quitting; application cleanup remains owned by the launcher."
                    )
                    return 0
                if choice.lower() in {"", "view", "status", "back", ":back"}:
                    continue
                selected = None
                if choice.isdecimal() and 1 <= int(choice) <= len(available):
                    selected = available[int(choice) - 1]
                else:
                    identifier = "export_logs" if choice.lower() == "export" else choice
                    selected = next(
                        (
                            action
                            for action in available
                            if action["action_id"] == identifier
                        ),
                        None,
                    )
                if selected is None:
                    self.write(
                        "Choose a displayed eligible action. Raw commands, paths and authority flags are not accepted."
                    )
                    continue
                operation_id = self.perform(view, selected)
                if operation_id:
                    self.monitor(operation_id)
            except _Back:
                self.write("Canceled before dispatch. No action was executed.")
            except EOFError:
                self.write("Input closed. No additional action was executed.")
                return 0
            except KeyboardInterrupt:
                self.write(
                    "Terminal interrupted. No robot emergency stop or power-off is implied. The launcher owns service cleanup."
                )
                return 0
            except Exception as error:
                self.write(f"Action stopped: {error}")
                self.write(
                    "Inspect current operations before considering another action; no retry was automatic."
                )


def run_terminal_wizard(
    service: WizardService,
    *,
    read_line: Callable[[str], str] = input,
    write_line: Callable[[str], Any] = print,
    sleep: Callable[[float], Any] = time.sleep,
) -> int:
    """Run the headless workbench; the caller alone owns service.shutdown()."""
    return _TerminalWizard(service, read_line, write_line, sleep).run()
