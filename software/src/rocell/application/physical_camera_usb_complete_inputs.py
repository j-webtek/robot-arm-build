"""Original-v13 data adapter for the complete-series verifier.

No filesystem authentication is performed here. The original owner must supply
the complete audited v13 prefix and independently bound received subjects, then
verify the returned inputs with the complete-series codec. A diagnostic export
or a structurally shaped dictionary is not an authenticated original store.
"""

from typing import Any

from rocell.application.physical_camera_usb_absence import _record
from rocell.application.physical_camera_usb_reboot import (
    original_usb_reboot_predecessor_v13,
    _original_usb_reboot_predecessor,
)
from .physical_camera_usb_complete_constants import SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA
from rocell.application.physical_camera_usb_reboot_constants import (
    SOURCE_WORKFLOW_USB_REBOOT_SCHEMA,
    USB_REBOOT_ROLE_BYTES,
)
from rocell.application.commissioning_usb_identity_persistence import (
    decode_physical_usb_identity_permit,
)
from rocell.providers.windows.usb_identity_protocol import canonical, digest


class CompleteUsbInputsError(ValueError):
    """Closed invalid-input failure without raw original identifiers."""


def _need(ok: bool) -> None:
    if not ok:
        raise CompleteUsbInputsError("USB_COMPLETE_ORIGINAL_INPUTS_INVALID")


def original_usb_complete_inputs(
    workflow: dict[str, Any], *, received: dict[str, Any]
) -> dict[str, Any]:
    """Extract independently retained final roles; never edit or relabel them."""
    return _original_usb_complete_inputs(
        workflow, received=received, complete_successor=False
    )


def original_usb_complete_inputs_v14(
    workflow: dict[str, Any], *, received: dict[str, Any]
) -> dict[str, Any]:
    """Exact v14 input join after the owner's full original audit, not authority.

    A separate path preserves the old v13 adapter's closed schema contract.
    Original records and the current schema are passed unchanged throughout.
    """
    _need(
        type(workflow) is dict
        and type(workflow.get("usb_qualification_complete")) is dict
    )
    return _original_usb_complete_inputs(
        workflow, received=received, complete_successor=True
    )


def _original_usb_complete_inputs(workflow, *, received, complete_successor):
    try:
        _need(
            type(workflow) is dict
            and type(complete_successor) is bool
            and workflow.get("schema")
            == (
                SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA
                if complete_successor
                else SOURCE_WORKFLOW_USB_REBOOT_SCHEMA
            )
        )
        phase = workflow["usb_qualification_reboot"]
        _need(
            type(phase) is dict
            and phase["phase"] == "AFTER_REBOOT"
            and phase["state"] == "RETAINED_BLOCKED"
        )
        records = {role: _record(phase[role]) for role in USB_REBOOT_ROLE_BYTES}
        _need(
            all(
                len(raw) <= USB_REBOOT_ROLE_BYTES[role]
                for role, (raw, _) in records.items()
            )
            and len({ref.evidence_id for _, ref in records.values()}) == len(records)
        )
        campaign = phase["original_campaign"]
        _need(
            type(campaign) is dict
            and set(campaign)
            == {
                "permit",
                "result",
                "admission_evidence",
                "evidence",
                "evidence_sha256",
                "reference",
                "retention",
            }
            and campaign["retention"] == "M1_FULL_BYTES_READ_BACK"
            and type(campaign["admission_evidence"]) is dict
            and type(campaign["result"]) is dict
            and campaign["result"]["state"] == "SEALED_KNOWN"
            and campaign["result"]["quarantine_latched"] is False
            and canonical(campaign["evidence"]) == records["execution"][0]
            and campaign["evidence_sha256"] == digest(records["execution"][0])
        )
        permit = decode_physical_usb_identity_permit(campaign["permit"])
        _need(
            campaign["result"]["attempt_id"] == permit.attempt_id
            and campaign["result"]["permit_sha256"] == permit.permit_sha256
        )
        predecessor = (
            _original_usb_reboot_predecessor(
                workflow, received=received, successor=True, complete_successor=True
            )
            if complete_successor
            else original_usb_reboot_predecessor_v13(workflow, received=received)
        )
        roles = (
            ("operation", "operation"),
            ("operator_event", "operator_event"),
            ("native_enrollment", "enrollment"),
            ("owned_usb_run", "execution"),
            ("host_boot", "host_boot"),
        )
        return dict(
            predecessor=predecessor,
            reboot_payload=records["phase_record"][0],
            reboot_reference=records["phase_record"][1],
            reboot_permit=permit,
            reboot_sources={name: records[stored][0] for name, stored in roles},
            reboot_references={name: records[stored][1] for name, stored in roles},
        )
    except CompleteUsbInputsError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        IndexError,
        RecursionError,
    ) as exc:
        raise CompleteUsbInputsError("USB_COMPLETE_ORIGINAL_INPUTS_INVALID") from exc
