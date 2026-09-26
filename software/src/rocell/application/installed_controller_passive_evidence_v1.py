"""Passive installed-controller evidence candidate assembly.

This boundary consumes one already captured, read-only HTTP identity response and
retained local originals.  It performs no network, serial, firmware, or motion
I/O and deliberately cannot create approved qualification evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
from typing import Any, Mapping


SCHEMA = "rocell.installed_controller_passive_evidence.v1"
CAPABILITIES_SCHEMA = "rocell.registration_ladder.v1"
EXPECTED_INSTALL_STAGES = (
    "RESERVED",
    "IDENTITY_AND_PREWRITE_VERIFIED",
    "WRITE_ATTEMPT_STARTED",
    "FLASH_VERIFIED",
    "ONE_STARTUP_ATTEMPT",
    "STARTUP_RESET_SENT",
)
BLOCKERS = (
    "INDEPENDENT_REVIEW_REQUIRED",
    "RUNTIME_APP_HASH_NOT_ATTESTED",
    "JOINT_MAPPING_EVIDENCE_NOT_BOUND",
    "PROTOCOL_EVIDENCE_NOT_BOUND",
    "STARTUP_BEHAVIOR_REVIEW_NOT_BOUND",
    "FEEDBACK_PROTOCOL_REVIEW_NOT_BOUND",
    "CONFIGURATION_EPOCH_NOT_ESTABLISHED",
)
_BOOT_ID = re.compile(r"^[0-9a-f]{32}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CAPABILITIES_KEYS = {
    "schema", "boot_id", "maximum_legs", "automatic_progression",
    "gripper_writes", "motion_authorized",
}


class InstalledControllerPassiveEvidenceError(ValueError):
    """A retained original or passive observation is malformed or inconsistent."""


def canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise InstalledControllerPassiveEvidenceError(
            "evidence value is not canonical JSON") from exc


def sha256_bytes(value: bytes) -> str:
    if not isinstance(value, bytes):
        raise TypeError("evidence originals must be bytes")
    return hashlib.sha256(value).hexdigest()


def _json_object(value: bytes, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstalledControllerPassiveEvidenceError(
            f"{label} is not one UTF-8 JSON object") from exc
    if type(parsed) is not dict:
        raise InstalledControllerPassiveEvidenceError(f"{label} must be an object")
    return parsed


def _validate_capabilities(value: Mapping[str, Any]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != _CAPABILITIES_KEYS:
        raise InstalledControllerPassiveEvidenceError(
            "live capabilities fields differ from the reviewed r96 surface")
    boot = value.get("boot_id")
    if (
        value.get("schema") != CAPABILITIES_SCHEMA
        or not isinstance(boot, str) or _BOOT_ID.fullmatch(boot) is None
        or value.get("maximum_legs") != 1
        or value.get("automatic_progression") is not False
        or value.get("gripper_writes") is not False
        or value.get("motion_authorized") is not False
    ):
        raise InstalledControllerPassiveEvidenceError(
            "live capabilities do not describe the bounded exhausted r96 surface")
    return dict(value)


def _validate_timestamp(value: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise InstalledControllerPassiveEvidenceError(
            "capture timestamp must be UTC text ending in Z")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise InstalledControllerPassiveEvidenceError(
            "capture timestamp is invalid") from exc
    return value


@dataclass(frozen=True, slots=True)
class InstalledControllerPassiveEvidenceV1:
    capture_id: str
    captured_at_utc: str
    controller_session_id: str
    usb_port: str
    usb_pnp_instance_id: str
    installed_app_sha256: str
    installed_app_bytes_sha256: str
    deployment_journal_sha256: str
    final_export_manifest_sha256: str
    final_feedback_attachment_sha256: str
    live_capabilities: Mapping[str, Any]
    live_capabilities_sha256: str
    schema: str = SCHEMA

    def __post_init__(self) -> None:
        if self.schema != SCHEMA:
            raise InstalledControllerPassiveEvidenceError("unsupported evidence schema")
        if not isinstance(self.capture_id, str) or not self.capture_id:
            raise InstalledControllerPassiveEvidenceError("capture_id is required")
        _validate_timestamp(self.captured_at_utc)
        if _BOOT_ID.fullmatch(self.controller_session_id) is None:
            raise InstalledControllerPassiveEvidenceError(
                "controller_session_id must be the observed boot id")
        if not isinstance(self.usb_port, str) or not re.fullmatch(r"COM[1-9][0-9]{0,3}", self.usb_port):
            raise InstalledControllerPassiveEvidenceError("usb_port is invalid")
        if not isinstance(self.usb_pnp_instance_id, str) or not self.usb_pnp_instance_id:
            raise InstalledControllerPassiveEvidenceError("USB PnP identity is required")
        for name in (
            "installed_app_sha256", "installed_app_bytes_sha256",
            "deployment_journal_sha256", "final_export_manifest_sha256",
            "final_feedback_attachment_sha256", "live_capabilities_sha256",
        ):
            if _SHA256.fullmatch(getattr(self, name)) is None:
                raise InstalledControllerPassiveEvidenceError(f"{name} is invalid")
        capabilities = _validate_capabilities(self.live_capabilities)
        if capabilities["boot_id"] != self.controller_session_id:
            raise InstalledControllerPassiveEvidenceError(
                "live boot differs from controller session")
        if sha256_bytes(canonical_json(capabilities)) != self.live_capabilities_sha256:
            raise InstalledControllerPassiveEvidenceError(
                "live capabilities hash differs")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "capture_id": self.capture_id,
            "captured_at_utc": self.captured_at_utc,
            "controller_session_id": self.controller_session_id,
            "usb_identity": {
                "port": self.usb_port,
                "pnp_instance_id": self.usb_pnp_instance_id,
            },
            "retained_originals": {
                "installed_app_sha256": self.installed_app_sha256,
                "installed_app_bytes_sha256": self.installed_app_bytes_sha256,
                "deployment_journal_sha256": self.deployment_journal_sha256,
                "final_export_manifest_sha256": self.final_export_manifest_sha256,
                "final_feedback_attachment_sha256": self.final_feedback_attachment_sha256,
            },
            "live_capabilities": dict(self.live_capabilities),
            "live_capabilities_sha256": self.live_capabilities_sha256,
            "observation_method": "ONE_HTTP_GET_NO_RETRY",
            "serial_port_opened": False,
            "controller_restarted": False,
            "hardware_writes": 0,
            "movement_commands": 0,
            "review_disposition": "UNREVIEWED",
            "qualification_evidence_ready": False,
            "blockers": list(BLOCKERS),
            "execution_authorized": False,
            "transport_authorized": False,
            "physical_authority": False,
        }

    @property
    def evidence_sha256(self) -> str:
        return sha256_bytes(canonical_json(self.unsigned_dict()))

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "evidence_sha256": self.evidence_sha256}


def assemble_installed_controller_passive_evidence_v1(
    *, capture_id: str, captured_at_utc: str, usb_port: str,
    usb_pnp_instance_id: str, installed_app_bytes: bytes,
    deployment_journal_bytes: bytes, final_export_manifest_bytes: bytes,
    final_feedback_attachment_bytes: bytes,
    live_capabilities: Mapping[str, Any],
) -> InstalledControllerPassiveEvidenceV1:
    """Correlate passive identity with retained originals; grant no authority."""

    capabilities = _validate_capabilities(live_capabilities)
    app_sha = sha256_bytes(installed_app_bytes)
    journal_rows: list[dict[str, Any]] = []
    try:
        for line in deployment_journal_bytes.decode("utf-8").splitlines():
            row = json.loads(line)
            if type(row) is not dict:
                raise TypeError
            journal_rows.append(row)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise InstalledControllerPassiveEvidenceError(
            "deployment journal is not JSONL objects") from exc
    if tuple(row.get("stage") for row in journal_rows) != EXPECTED_INSTALL_STAGES:
        raise InstalledControllerPassiveEvidenceError(
            "deployment journal stages differ from the one-attempt install")
    if (
        journal_rows[0].get("app_sha256") != app_sha
        or journal_rows[3].get("app_sha256") != app_sha
        or journal_rows[3].get("protected_regions_unchanged") is not True
    ):
        raise InstalledControllerPassiveEvidenceError(
            "installed app or protected-region evidence differs")
    manifest = _json_object(final_export_manifest_bytes, "final export manifest")
    attachment = _json_object(
        final_feedback_attachment_bytes, "final feedback attachment")
    boot = capabilities["boot_id"]
    if (
        manifest.get("complete") is not True
        or manifest.get("kind") != "DIAGNOSTIC_ONLY"
        or manifest.get("physical_authority") != "NONE"
        or attachment.get("schema") != "rocell.registration_ladder_leg_attempt.v1"
        or attachment.get("boot_id") != boot
        or attachment.get("app_sha256") != app_sha
        or attachment.get("category") != "LEG_VERIFIED"
        or attachment.get("automatic_progression") is not False
        or attachment.get("retry_allowed") is not False
    ):
        raise InstalledControllerPassiveEvidenceError(
            "final export does not bind the same bounded boot and app")
    live_hash = sha256_bytes(canonical_json(capabilities))
    return InstalledControllerPassiveEvidenceV1(
        capture_id=capture_id,
        captured_at_utc=captured_at_utc,
        controller_session_id=boot,
        usb_port=usb_port,
        usb_pnp_instance_id=usb_pnp_instance_id,
        installed_app_sha256=app_sha,
        installed_app_bytes_sha256=app_sha,
        deployment_journal_sha256=sha256_bytes(deployment_journal_bytes),
        final_export_manifest_sha256=sha256_bytes(final_export_manifest_bytes),
        final_feedback_attachment_sha256=sha256_bytes(
            final_feedback_attachment_bytes),
        live_capabilities=capabilities,
        live_capabilities_sha256=live_hash,
    )


__all__ = [
    "BLOCKERS", "CAPABILITIES_SCHEMA", "EXPECTED_INSTALL_STAGES", "SCHEMA",
    "InstalledControllerPassiveEvidenceError",
    "InstalledControllerPassiveEvidenceV1",
    "assemble_installed_controller_passive_evidence_v1", "canonical_json",
    "sha256_bytes",
]
