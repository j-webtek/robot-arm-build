"""Derive expected camera traits from a reviewed enrollment, without device I/O.

The acquisition owner still authenticates retained originals and currentness.
Historical enrollment is never relabelled as a fresh launch or metadata query.
"""

from rocell.application.physical_camera_selection import (
    selection_from_enrollment_snapshot,
)
from rocell.application.wizard_native_camera_enrollment import (
    WizardNativeCameraEnrollment,
)
from rocell.application.wizard_native_camera_metadata import validate_native_packet
from rocell.providers.windows.camera_worker_client import (
    IDENTITY_PROTOCOL_SCHEMA,
    NativeCameraIdentityReceipt,
)
from rocell.providers.windows.native_camera_protocol import canonical
from rocell.providers.windows.native_camera_activation_expectation import (
    SCHEMA,
    CameraActivationExpectation,
    require,
)


def expectation_from_enrollment(
    enrollment: WizardNativeCameraEnrollment,
    *,
    source_sha256: str,
    launch_session_id: str,
) -> CameraActivationExpectation:
    require(
        type(enrollment) is WizardNativeCameraEnrollment, "ACTIVATION_EXACT_ENROLLMENT"
    )
    return expectation_from_enrollment_snapshot(
        enrollment.export_snapshot(),
        source_sha256=source_sha256,
        launch_session_id=launch_session_id,
    )


def expectation_from_enrollment_snapshot(
    snapshot: object, *, source_sha256: str, launch_session_id: str
) -> CameraActivationExpectation:
    """Verify saved metadata without constructing or relabelling a live owner.

    The original-record reader supplies the snapshot's independent provenance;
    this shared pure join establishes exactly the same traits as live enrollment.
    """
    # This existing selection reader recomputes the full metadata review join.
    # It does not turn a detached snapshot into an authenticated original store.
    selection = selection_from_enrollment_snapshot(
        snapshot, source_sha256=source_sha256, launch_session_id=launch_session_id
    )
    require(selection is not None, "ACTIVATION_REVIEWED_SELECTION_REQUIRED")
    assert selection is not None  # Narrow the independently checked result type.
    assert isinstance(snapshot, dict)  # The selection reader validated its shape.
    identity = selection.identity_document
    _, receipt = validate_native_packet(
        snapshot["identity_packet"],
        kind="identity",
        expected_endpoint=identity["symbolic_link"],
        **identity["metadata_review"]["provider"],
    )
    require(
        type(receipt) is NativeCameraIdentityReceipt
        and receipt.protocol_schema == IDENTITY_PROTOCOL_SCHEMA
        and receipt.driver is not None,
        "ACTIVATION_ORIGINAL_DRIVER_METADATA_REQUIRED",
    )
    assert isinstance(receipt, NativeCameraIdentityReceipt)
    require(
        receipt.exact_endpoint_observed
        and receipt.device is not None
        and receipt.chain_end == "REACHED_OBSERVED_ROOT"
        and bool(receipt.parents),
        "ACTIVATION_ORIGINAL_METADATA_INCOMPLETE",
    )
    node, driver = receipt.device, receipt.driver
    assert node is not None and driver is not None
    properties = (
        node.instance_id,
        node.container_id,
        node.location_paths,
        driver.provider,
        driver.service,
        driver.version,
        driver.inf_path,
    )
    require(
        all(item.observed for item in properties),
        "ACTIVATION_ORIGINAL_PROPERTY_UNAVAILABLE",
    )
    require(
        node.devnode == driver.devnode == receipt.devnode.value,
        "ACTIVATION_DETACHED_DRIVER",
    )
    paths = node.location_paths.value
    assert paths is not None
    return CameraActivationExpectation(
        canonical(
            dict(
                schema=SCHEMA,
                original_identity_sha256=identity["native_identity_sha256"],
                endpoint=identity["symbolic_link"],
                instance_id=node.instance_id.value,
                container_id=node.container_id.value,
                location_paths_json=canonical(
                    {f"path_{i:02d}": path for i, path in enumerate(paths)}
                ).decode("ascii"),
                driver_provider=driver.provider.value,
                driver_service=driver.service.value,
                driver_version=driver.version.value,
                driver_inf=driver.inf_path.value,
            )
        )
    )
