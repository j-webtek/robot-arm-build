"""Exact reviewed predecessor binding for the incapable serial campaign.

This is an internal data contract, not an approval or a device selector. The
service must first verify the original M1 receipt/assessment/review trios and
their substantive stage-9–11 reports. No browser-supplied hash, COM alias,
driver, firmware claim or power state is admitted here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any

from rocell.application.physical_connection_contracts import (
    EvidenceOrigin,
    RoArmUsbSerialIdentity,
    UsbDriverIdentity,
    canonical_sha256,
)
from rocell.providers.windows.arm_feedback_worker import ReviewedControllerBinding


SCHEMA = "rocell.rehearsal_feedback_binding.v1"
NATIVE_FIXTURE_SCHEMA = "rocell.rehearsal_feedback_binding.v2"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ACTOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_PREDECESSORS = ("arm_identity", "power_safety", "power_on_observation")


def _digest(value: object) -> None:
    if type(value) is not str or not _HASH.fullmatch(value) or value == "0" * 64:
        raise ValueError("An exact nonzero predecessor/source digest is required")


@dataclass(frozen=True, slots=True)
class ReviewedFeedbackPredecessor:
    stage: str
    receipt_sha256: str
    assessment_sha256: str
    review_sha256: str
    evaluation_sha256: str

    def __post_init__(self) -> None:
        if type(self.stage) is not str or self.stage not in _PREDECESSORS:
            raise ValueError("Only the exact arm identity and power stages are inputs")
        for name in (
            "receipt_sha256",
            "assessment_sha256",
            "review_sha256",
            "evaluation_sha256",
        ):
            _digest(getattr(self, name))

    def to_dict(self) -> dict[str, str]:
        return {
            "stage": self.stage,
            "receipt_sha256": self.receipt_sha256,
            "assessment_sha256": self.assessment_sha256,
            "review_sha256": self.review_sha256,
            "evaluation_sha256": self.evaluation_sha256,
        }


@dataclass(frozen=True, slots=True)
class RehearsalFeedbackBinding:
    workspace_source_sha256: str
    catalog_sha256: str
    cell_id: str
    session_id: str
    operator_id: str
    predecessors: tuple[ReviewedFeedbackPredecessor, ...]
    controller: ReviewedControllerBinding
    generic_reviewed_controller: ReviewedControllerBinding | None = None

    def __post_init__(self) -> None:
        _digest(self.workspace_source_sha256)
        _digest(self.catalog_sha256)
        for name in ("cell_id", "session_id", "operator_id"):
            value = getattr(self, name)
            pattern = _ACTOR if name == "operator_id" else _ID
            if type(value) is not str or not pattern.fullmatch(value):
                raise ValueError(
                    "An exact bounded session/operator identifier is required"
                )
        if (
            type(self.predecessors) is not tuple
            or len(self.predecessors) != 3
            or any(
                type(item) is not ReviewedFeedbackPredecessor
                for item in self.predecessors
            )
            or tuple(item.stage for item in self.predecessors) != _PREDECESSORS
        ):
            raise ValueError(
                "Exactly the ordered stage-9–11 reviewed inputs are required"
            )
        if (
            type(self.controller) is not ReviewedControllerBinding
            or self.controller.origin is not EvidenceOrigin.SYNTHETIC_REHEARSAL
            or self.controller.identity_receipt_sha256
            != self.predecessors[0].receipt_sha256
        ):
            raise ValueError(
                "The incapable controller must bind the reviewed identity receipt"
            )
        if self.generic_reviewed_controller is not None:
            # The new owned lane models a native interface explicitly. Retain
            # the original generic review as a separate subject, not an invented
            # observation that Windows reported a native interface or driver.
            from rocell.providers.windows.incapable_controller_metadata import (
                synthetic_native_identity,
            )

            generic = self.generic_reviewed_controller
            if (
                type(generic) is not ReviewedControllerBinding
                or generic.origin is not EvidenceOrigin.SYNTHETIC_REHEARSAL
                or self.controller
                != replace(generic, identity=synthetic_native_identity(generic))
            ):
                raise ValueError("Exact modeled native controller lineage required")

    def to_dict(self) -> dict[str, Any]:
        document = {
            "schema": SCHEMA,
            "stage": "feedback_only_connection",
            "workspace_source_sha256": self.workspace_source_sha256,
            "catalog_sha256": self.catalog_sha256,
            "cell_id": self.cell_id,
            "session_id": self.session_id,
            "operator_id": self.operator_id,
            "predecessors": [item.to_dict() for item in self.predecessors],
            "controller": self.controller.to_dict(),
            "driver_firmware_boot_provenance": "EXPLICIT_UNMEASURED_FIXTURE_ONLY",
            "physical_authority": False,
        }
        if self.generic_reviewed_controller is not None:
            document.update(
                schema=NATIVE_FIXTURE_SCHEMA,
                generic_reviewed_controller=self.generic_reviewed_controller.to_dict(),
                transport_provenance="EXPLICIT_MODELED_WINDOWS_CM_METADATA_V1",
            )
        return document

    @property
    def binding_sha256(self) -> str:
        return canonical_sha256(self.to_dict())

    @property
    def selected_identity_document(self) -> dict[str, object]:
        # Admission hashes precisely this transport identity, not a camera or
        # its ephemeral COM alias alone. It still identifies only memory data.
        return self.controller.identity.to_dict()


def owned_metadata_feedback_binding(
    binding: RehearsalFeedbackBinding,
) -> RehearsalFeedbackBinding:
    """Pure v2 fixture binding before admission; never migrate a retained v1.

    The same modeled transport is reconstructed during historical verification
    only when the original owned operation explicitly names the new IPC version.
    No device enumeration or physical binding approval happens here.
    """
    from rocell.providers.windows.incapable_controller_metadata import (
        synthetic_native_identity,
    )

    if type(binding) is not RehearsalFeedbackBinding:
        raise ValueError("Exact rehearsal feedback binding required")
    binding.__post_init__()
    if binding.generic_reviewed_controller is not None:
        raise ValueError("A modeled native binding cannot be adapted a second time")
    return replace(
        binding,
        controller=replace(
            binding.controller, identity=synthetic_native_identity(binding.controller)
        ),
        generic_reviewed_controller=binding.controller,
    )


def controller_from_verified_arm_identity(
    report: dict[str, Any], *, identity_receipt_sha256: str
) -> ReviewedControllerBinding:
    """Adapt an already-pure-verified stage-nine report; never enumerate the OS.

    The closed fixture comparison is defense in depth, not a substitute for the
    caller's independent report digest/source verification. Missing driver and
    installed firmware observations remain conspicuously UNMEASURED fixtures.
    """
    _digest(identity_receipt_sha256)
    if report.get("outcome") != "REHEARSAL_CHECKS_PASSED":
        raise ValueError("The reviewed identity report must pass its synthetic checks")
    reports = report["reports"]
    candidate = reports["selection_baseline"]["candidate"]
    usb = candidate["usb_identity"]
    if (
        usb != {"vid": "1234", "pid": "5678", "unit_serial": "INCAPABLE-ARM-001"}
        or candidate["os_instance_id"] != "USB VID:PID=1234:5678 SER=INCAPABLE-ARM-001"
        or candidate["persistent_ids"] != ["usb-unit:1234:5678:INCAPABLE-ARM-001"]
        or candidate["ephemeral_locator_observation"] != "COM42"
        or candidate["identity_blockers"] != []
        or candidate["qualified"] is not False
        or candidate["selection_performed"] is not False
    ):
        raise ValueError(
            "Only the exact reviewed incapable controller fixture is supported"
        )
    profile_hash = reports["profile"]["profile_file_sha256"]
    _digest(profile_hash)
    identity = RoArmUsbSerialIdentity(
        usb["vid"],
        usb["pid"],
        usb["unit_serial"],
        candidate["os_instance_id"],
        candidate["persistent_ids"][0],
        candidate["ephemeral_locator_observation"],
        UsbDriverIdentity(
            "SYNTHETIC_UNMEASURED",
            "memory-only",
            "UNMEASURED",
            "synthetic-not-installed.inf",
        ),
    )

    def unmeasured(label: str) -> str:
        return canonical_sha256(
            {
                "fixture_only": label,
                "reviewed_arm_identity_receipt_sha256": identity_receipt_sha256,
                "physical_observation": False,
            }
        )

    return ReviewedControllerBinding(
        identity=identity,
        identity_receipt_sha256=identity_receipt_sha256,
        arm_model_receipt_sha256=unmeasured("MODEL_NOT_RECEIVED_PRO_FIXTURE"),
        installed_firmware_evidence_sha256=unmeasured(
            "INSTALLED_FIRMWARE_NOT_ACQUIRED"
        ),
        boot_policy_evidence_sha256=unmeasured("BOOT_POLICY_NOT_PHYSICALLY_OBSERVED"),
        serial_profile_sha256=profile_hash,
        origin=EvidenceOrigin.SYNTHETIC_REHEARSAL,
    )
