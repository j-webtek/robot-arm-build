"""Authenticate the full original v15 predecessor before a v16 preparation.

The Session owner supplies actual retained packages and the unchanged snapshot.
The functions here neither read arbitrary paths nor issue camera permissions.
Fresh runtime files, physical conditions and capacity are checked at dispatch.
"""

from pathlib import Path
from typing import Any

from .camera_probe_preparation import (
    SOURCE_WORKFLOW_PROBE_SCHEMA,
    CameraProbePreparation,
)
from .camera_probe_preparation_layout import (
    verify_camera_probe_preparation_layout,
    _original_record,
)
from .physical_camera_mode_entry import SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA
from .physical_camera_mode_entry_readback import _verify_camera_mode_entry_prefix
from .physical_camera_selection import selection_from_enrollment_snapshot


class CameraProbeOriginalError(ValueError):
    def __init__(self) -> None:
        super().__init__("CAMERA_PROBE_PREPARATION_ORIGINAL_INVALID")


def _need(ok: bool) -> None:
    if not ok:
        raise CameraProbeOriginalError()


def read_camera_probe_preparation_layout(snapshot, mode_packages, probe_packages):
    try:
        _need(type(mode_packages) is dict and len(mode_packages) == 1)
        evidence_id, package = next(iter(mode_packages.items()))
        _need(type(package) is dict and set(package) == {"entry_id", "record"})
        record = package["record"]
        _need(
            record["reference"]["evidence_id"] == evidence_id
            and package["entry_id"] == record["document"]["entry_id"]
        )
        return verify_camera_probe_preparation_layout(snapshot, record, probe_packages)
    except CameraProbeOriginalError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
        raise CameraProbeOriginalError() from error


def _verify_current_subject_context(original, layout, bound):
    """Compare against the independently authenticated predecessor, not itself."""
    _compare_preparation_context(original, layout.preparation.to_dict(), bound)


def verify_probe_preparation_context(original, preparation, bound):
    """Check a newly built subject before retention; caller authenticates originals.

    No layout is invented for a record that has not yet been stored. The original
    reader uses the identical comparison after it verifies its actual layout.
    """
    _need(type(preparation) is CameraProbePreparation)
    _compare_preparation_context(original, preparation.to_dict(), bound)


def _compare_preparation_context(original, prep, bound):
    _need(original["schema"] == SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA)
    entry = original["camera_mode_entry"]
    plan = prep["plan"]
    _need(
        entry["state"] == "ENTERED"
        and len(entry["events"]) == 1
        and prep["entry_sha256"] == entry["entry"]["evidence_sha256"]
        and prep["entry_event_sha256"] == entry["events"][0]["event_sha256"]
        and all(
            plan[key] == bound[key]
            for key in ("workspace", "source_sha256", "cell_id", "session_id")
        )
        and plan["assigned_parent_directory"]
        == str(Path(bound["directory"]) / "native-camera-output")
    )
    previous = original["usb_qualification_reboot"]["enrollment"]["document"]
    old_launch = previous["view"]["provenance"]["session_id"]
    old = selection_from_enrollment_snapshot(
        previous, source_sha256=bound["source_sha256"], launch_session_id=old_launch
    )
    current = selection_from_enrollment_snapshot(
        prep["enrollment"],
        source_sha256=bound["source_sha256"],
        launch_session_id=plan["launch_session_id"],
    )
    _need(old is not None and current is not None)
    assert old is not None and current is not None
    before, after = old.identity_document, current.identity_document
    _need(before["symbolic_link"] == after["symbolic_link"])
    _need(
        all(
            before["metadata_review"][key] == after["metadata_review"][key]
            for key in ("observed_instance_id", "observed_container_id")
        )
    )
    old_receipt = previous["identity_packet"]["receipt"]
    current_receipt = prep["enrollment"]["identity_packet"]["receipt"]
    # A new port/topology or changed USB unit/driver needs new qualification,
    # not merely another self-consistent enrollment. Devnode numbers are
    # ephemeral and deliberately are not used as persistent unit identity.
    _need(
        old_receipt["device"]["location_paths"]
        == current_receipt["device"]["location_paths"]
    )
    _need(
        previous["generic_review"]["candidate_record"]["usb_identity"]
        == prep["enrollment"]["generic_review"]["candidate_record"]["usb_identity"]
    )
    if old_receipt.get("driver") is not None:
        for key in ("provider", "service", "version", "inf_path"):
            if old_receipt["driver"][key]["availability"] == "OBSERVED":
                _need(old_receipt["driver"][key] == current_receipt["driver"][key])
    # The old accepted enrollment keeps its old launch/operation identities.
    # A new preparation must use separately collected metadata operations.
    fields = {"generic_operation_id", "inventory_operation_id", "identity_operation_id"}
    old_ids: set[str] = set()
    pending = [original]
    while pending:
        node = pending.pop()
        if type(node) is dict:
            old_ids.update(
                value
                for key, value in node.items()
                if key in fields and type(value) is str
            )
            pending.extend(node.values())
        elif type(node) is list:
            pending.extend(node)
    new_ids = {after["metadata_review"][key] for key in fields}
    _need(len(new_ids) == 3 and not old_ids.intersection(new_ids))


def verify_camera_probe_preparation_workflow(
    bound,
    snapshot,
    expected_header_sha256,
    roles,
    intake_packages,
    qualification_packages,
    qualification_originals,
    static_packages,
    received_packages,
    received_originals,
    identity_packages,
    usb_packages,
    trial_packages,
    phase_packages,
    absence_packages,
    reconnect_packages,
    reboot_packages,
    complete_packages,
    mode_packages,
    probe_packages,
    *,
    original_campaigns=(),
    original_presence_campaigns=(),
) -> dict[str, Any]:
    layout = read_camera_probe_preparation_layout(
        snapshot, mode_packages, probe_packages
    )
    original = _verify_camera_mode_entry_prefix(
        bound,
        snapshot,
        expected_header_sha256,
        roles,
        intake_packages,
        qualification_packages,
        qualification_originals,
        static_packages,
        received_packages,
        received_originals,
        identity_packages,
        usb_packages,
        trial_packages,
        phase_packages,
        absence_packages,
        reconnect_packages,
        reboot_packages,
        complete_packages,
        layout,
        original_campaigns=original_campaigns,
        original_presence_campaigns=original_presence_campaigns,
    )
    return _camera_probe_workflow(original, layout, bound)


def _camera_probe_workflow(original, layout, bound):
    """Project the verified prefix, reused by its closed operating successor."""
    try:
        _verify_current_subject_context(original, layout, bound)
        return {
            **original,
            "schema": SOURCE_WORKFLOW_PROBE_SCHEMA,
            "camera_probe_preparation": {
                "state": layout.state,
                "preparation": _original_record(
                    layout.preparation, layout.preparation_reference
                ),
                "review": (
                    None
                    if layout.review is None
                    else _original_record(layout.review, layout.review_reference)
                ),
                "events": [event.to_dict() for event in layout.events],
                "meaning": "Original preparation/review only; current runtime, capacity, physical conditions and camera admission remain separate. No camera or arm was opened by this record.",
            },
        }
    except CameraProbeOriginalError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
        raise CameraProbeOriginalError() from error
