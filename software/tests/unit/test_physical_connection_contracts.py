from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib

import pytest

from rocell.application.physical_connection_contracts import (
    B0477_CLOSE_RECEIPT_SCHEMA,
    B0477_CONFIGURATION_RECEIPT_SCHEMA,
    B0477_DISCOVERY_RECEIPT_SCHEMA,
    B0477_FLUSH_RECEIPT_SCHEMA,
    B0477_FRAME_RECEIPT_SCHEMA,
    B0477_REOPEN_RECEIPT_SCHEMA,
    HOST_DEPENDENCY_RECEIPT_SCHEMA,
    ROARM_T105_RECEIPT_SCHEMA,
    ROARM_UNPOWERED_IDENTITY_RECEIPT_SCHEMA,
    B0477ConnectionProvider,
    B0477DiscoveryRequest,
    B0477ExactConfiguration,
    B0477ManualControls,
    B0477UvcIdentity,
    CameraCloseRequest,
    CameraConfigurationRequest,
    CameraFlushRequest,
    CameraOpenRequest,
    CameraReopenRequest,
    CapturedFrame,
    DependencyObservation,
    DependencyRequirement,
    DeterministicFakeB0477ConnectionProvider,
    DeterministicFakeHostDependencyProvider,
    DeterministicFakeRoArmConnectionProvider,
    EvidenceOrigin,
    FAKE_PROVIDER_DESCRIPTOR,
    FakeConnectionBoundaryError,
    FeedbackOnlyRoArmConnectionProvider,
    FrameTimingBasis,
    FreshFrameReceipt,
    FreshFrameRequest,
    HostDependencyProvider,
    HostDependencyRequest,
    HostIdentity,
    MAX_IMMUTABLE_FRAME_BYTES,
    PhysicalConnectionContractError,
    RoArmUsbSerialIdentity,
    RetainedFrameEncoding,
    SingleT105FeedbackReceipt,
    SingleT105FeedbackRequest,
    T105TransactionTiming,
    UnpoweredArmIdentityReceipt,
    UnpoweredArmIdentityRequest,
    Usb3Topology,
    UsbDriverIdentity,
    canonical_sha256,
)


RUN_ID = "connection-contract-test-run"
DIGEST = "1" * 64


def _driver(service: str = "usbvideo") -> UsbDriverIdentity:
    return UsbDriverIdentity(
        provider="Synthetic Vendor",
        service=service,
        version="0.0.synthetic",
        package_or_inf_path="synthetic://driver/package.inf",
    )


def _camera_identity() -> B0477UvcIdentity:
    return B0477UvcIdentity(
        vid="ffff",
        pid="0001",
        unit_serial="SYNTHETIC-B0477-UNIT-001",
        persistent_os_path="synthetic://pnp/camera/b0477/unit-001",
        device_instance_id="USB\\VID_FFFF&PID_0001\\SYNTHETIC-B0477-UNIT-001",
        driver=_driver(),
        topology=Usb3Topology(
            host_controller_instance_id="PCI\\SYNTHETIC-XHCI-CONTROLLER-001",
            hub_instance_path=("USB\\ROOT_HUB30\\SYNTHETIC-001",),
            port_chain=(3,),
            negotiated_speed_mbps=5_000,
            negotiated_generation="USB_3_2_GEN_1",
        ),
    )


def _arm_identity(
    *, persistent_port_path: str = "synthetic://ports/roarm/unit-001"
) -> RoArmUsbSerialIdentity:
    return RoArmUsbSerialIdentity(
        vid="ffff",
        pid="0002",
        unit_serial="SYNTHETIC-ROARM-M3-PRO-001",
        persistent_instance_id="USB\\VID_FFFF&PID_0002\\SYNTHETIC-ROARM-001",
        persistent_port_path=persistent_port_path,
        port_name="COM99",
        driver=_driver("usbser"),
    )


def _response() -> bytes:
    return (
        b'{"T":1051,"x":120.0,"y":0.0,"z":180.0,"b":0.1,'
        b'"s":0.2,"e":0.3,"t":0.4,"r":0.5,"g":0.6,'
        b'"tB":1,"tS":2,"tE":3,"tT":4,"tR":5,"tG":6,'
        b'"torswitchB":0,"torswitchS":0,"torswitchE":0,'
        b'"torswitchT":0,"torswitchR":0,"torswitchG":0,"v":1200}\n'
    )


def _fresh_receipt(payload: bytes = b"synthetic-encoded-frame") -> FreshFrameReceipt:
    return FreshFrameReceipt(
        run_id=RUN_ID,
        session_id="camera-session-001",
        provider_descriptor_sha256=FAKE_PROVIDER_DESCRIPTOR.descriptor_sha256,
        request_sha256="a" * 64,
        flush_receipt_sha256="b" * 64,
        configuration_sha256="c" * 64,
        sequence=12,
        capture_started_monotonic_ns=100,
        delivered_monotonic_ns=105,
        timing_basis=FrameTimingBasis.HOST_BRACKET,
        device_exposure_proof_sha256=None,
        retained_encoding=RetainedFrameEncoding.SYNTHETIC_CANONICAL_JSON,
        payload_bytes=len(payload),
        payload_sha256=hashlib.sha256(payload).hexdigest(),
    )


def _host_provider() -> tuple[
    DeterministicFakeHostDependencyProvider, HostDependencyRequest
]:
    requirements = (
        DependencyRequirement("opencv-contrib-python", ">=4.12,<5", True),
        DependencyRequirement("pyserial", ">=3.5,<4", True),
    )
    observations = {
        item.name: DependencyObservation(
            name=item.name,
            installed_version=(
                "4.12.0+synthetic"
                if item.name == "opencv-contrib-python"
                else "3.5.0+synthetic"
            ),
            artifact_path=f"synthetic://packages/{item.name}",
            artifact_sha256=hashlib.sha256(item.name.encode()).hexdigest(),
            available=True,
        )
        for item in requirements
    }
    host = HostIdentity(
        host_id="SYNTHETIC-HOST-001",
        os_name="Windows",
        os_release="synthetic",
        architecture="AMD64",
        python_implementation="CPython",
        python_version="3.12.synthetic",
        python_executable="synthetic://python/python.exe",
        python_executable_sha256="2" * 64,
    )
    request = HostDependencyRequest(RUN_ID, "3" * 64, requirements)
    return DeterministicFakeHostDependencyProvider(host, observations), request


def test_host_dependency_receipt_is_exact_hash_bound_and_synthetic() -> None:
    provider, request = _host_provider()

    receipt = provider.inspect_host_dependencies(request)

    assert isinstance(provider, HostDependencyProvider)
    assert receipt.schema == HOST_DEPENDENCY_RECEIPT_SCHEMA
    assert receipt.request_sha256 == request.request_sha256
    assert receipt.source_tree_sha256 == request.source_tree_sha256
    assert receipt.all_required_available is True
    assert len(receipt.receipt_sha256) == 64
    assert receipt.receipt_sha256 == canonical_sha256(receipt.to_dict())
    assert provider.descriptor.evidence_origin is EvidenceOrigin.SYNTHETIC_REHEARSAL
    assert provider.descriptor.hardware_capable is False


def test_host_request_and_observations_require_exact_sorted_field_set() -> None:
    with pytest.raises(PhysicalConnectionContractError, match="sorted"):
        HostDependencyRequest(
            RUN_ID,
            DIGEST,
            (
                DependencyRequirement("z-last", ">=1"),
                DependencyRequirement("a-first", ">=1"),
            ),
        )

    provider, request = _host_provider()
    provider._observations.pop("pyserial")  # type: ignore[attr-defined]
    with pytest.raises(FakeConnectionBoundaryError, match="exactly cover"):
        provider.inspect_host_dependencies(request)


def test_dependency_contract_rejects_invalid_pep440_inputs() -> None:
    with pytest.raises(PhysicalConnectionContractError, match="PEP 440 version specifier"):
        DependencyRequirement("opencv-contrib-python", "not-a-specifier")

    with pytest.raises(PhysicalConnectionContractError, match="PEP 440 version"):
        DependencyObservation(
            name="opencv-contrib-python",
            installed_version="0.0.synthetic",
            artifact_path="synthetic://packages/opencv-contrib-python",
            artifact_sha256=DIGEST,
            available=True,
        )


def test_required_dependency_outside_declared_version_range_cannot_pass() -> None:
    provider, request = _host_provider()
    original = provider._observations["opencv-contrib-python"]  # type: ignore[attr-defined]
    provider._observations["opencv-contrib-python"] = replace(  # type: ignore[attr-defined]
        original,
        installed_version="4.11.9",
    )

    receipt = provider.inspect_host_dependencies(request)

    assert receipt.all_required_available is False
    with pytest.raises(
        PhysicalConnectionContractError,
        match="does not match dependency observations",
    ):
        replace(receipt, all_required_available=True)


@pytest.mark.parametrize(
    "selector",
    ["0", "camera:0", "index 12", "/dev/video0", "COM9"],
)
def test_numeric_camera_or_com_only_selectors_are_never_persistent(
    selector: str,
) -> None:
    camera = _camera_identity()
    with pytest.raises(PhysicalConnectionContractError, match="persistent OS identity"):
        replace(camera, persistent_os_path=selector)

    with pytest.raises(PhysicalConnectionContractError, match="persistent OS identity"):
        _arm_identity(persistent_port_path=selector)


def test_camera_identity_binds_vid_pid_serial_driver_and_usb3_topology() -> None:
    identity = _camera_identity()
    content = identity.to_dict()

    assert content["manufacturer"] == "Arducam"
    assert content["model"] == "B0477"
    assert content["sensor"] == "Sony IMX283"
    assert content["vid"] == "ffff"
    assert content["pid"] == "0001"
    assert content["unit_serial"] == "SYNTHETIC-B0477-UNIT-001"
    assert content["driver"] == _driver().to_dict()
    assert content["topology"] == identity.topology.to_dict()
    assert identity.topology.negotiated_speed_mbps == 5_000

    with pytest.raises(PhysicalConnectionContractError, match="USB 3.x"):
        replace(identity.topology, negotiated_generation="USB_2_0")


def test_camera_flow_proves_exact_mode_manual_readback_freshness_and_reopen() -> None:
    identity = _camera_identity()
    provider = DeterministicFakeB0477ConnectionProvider(identity)
    discovery_request = B0477DiscoveryRequest(RUN_ID, identity)
    discovery = provider.discover_exact_b0477(discovery_request)
    session = provider.open_selected_b0477(
        CameraOpenRequest(RUN_ID, discovery.receipt_sha256, identity)
    )
    desired = B0477ExactConfiguration(B0477ManualControls(8_000, 1.0, 5_000))
    configuration = provider.configure_exact_b0477(
        CameraConfigurationRequest(
            RUN_ID,
            session.receipt_sha256,
            identity.identity_sha256,
            session.session_id,
            desired,
        )
    )
    flush = provider.flush_b0477_buffers(
        CameraFlushRequest(RUN_ID, session.session_id, configuration.receipt_sha256)
    )
    captured = provider.capture_fresh_b0477_frame(
        FreshFrameRequest(
            RUN_ID,
            session.session_id,
            flush.receipt_sha256,
            desired.configuration_sha256,
            flush.last_discarded_sequence,
            flush.flush_completed_monotonic_ns,
            1_000,
        )
    )
    frame = captured.receipt
    reopen = provider.reopen_exact_b0477(
        CameraReopenRequest(RUN_ID, session, identity, desired)
    )

    assert isinstance(provider, B0477ConnectionProvider)
    assert discovery.schema == B0477_DISCOVERY_RECEIPT_SCHEMA
    assert discovery.ordinal_fallback_used is False
    assert configuration.schema == B0477_CONFIGURATION_RECEIPT_SCHEMA
    assert configuration.observed.mode.to_dict() == {
        "width_px": 5472,
        "height_px": 3648,
        "fps_numerator": 9,
        "fps_denominator": 1,
        "fourcc": "YUY2",
        "host_bus": "USB_3_X",
    }
    assert configuration.observed.controls.to_dict() == {
        "exposure_mode": "MANUAL",
        "exposure_us": 8000.0,
        "gain_mode": "MANUAL",
        "gain_relative": 1.0,
        "white_balance_mode": "MANUAL",
        "white_balance_kelvin": 5000.0,
    }
    assert configuration.fallback_negotiated is False
    assert flush.schema == B0477_FLUSH_RECEIPT_SCHEMA
    assert flush.buffer_empty_after is True
    assert frame.schema == B0477_FRAME_RECEIPT_SCHEMA
    assert frame.sequence > flush.last_discarded_sequence
    assert frame.delivered_monotonic_ns >= frame.capture_started_monotonic_ns
    assert frame.timing_basis is FrameTimingBasis.HOST_BRACKET
    assert frame.device_exposure_proof_sha256 is None
    assert frame.retained_encoding is RetainedFrameEncoding.SYNTHETIC_CANONICAL_JSON
    assert captured.payload
    assert hashlib.sha256(captured.payload).hexdigest() == frame.payload_sha256
    assert captured.carrier_sha256
    assert reopen.schema == B0477_REOPEN_RECEIPT_SCHEMA
    assert reopen.close_receipt.schema == B0477_CLOSE_RECEIPT_SCHEMA
    assert reopen.close_receipt.close_attempted is True
    assert reopen.close_receipt.close_succeeded is True
    assert reopen.reopened_session.session_id != session.session_id
    assert reopen.reopened_identity.identity_sha256 == identity.identity_sha256
    assert (
        reopen.configuration_readback.observed.configuration_sha256
        == desired.configuration_sha256
    )

    close_request = CameraCloseRequest(
        RUN_ID,
        reopen.reopened_session,
        "ONBOARDING_STAGE_COMPLETE",
        reopen.configuration_readback.readback_monotonic_ns + 1,
    )
    first_close = provider.close_selected_b0477(close_request)
    repeated_close = provider.close_selected_b0477(close_request)
    assert first_close.close_attempted is True
    assert first_close.close_succeeded is True
    assert first_close.was_already_closed is False
    assert repeated_close.close_attempted is False
    assert repeated_close.close_succeeded is True
    assert repeated_close.was_already_closed is True
    assert repeated_close.close_completed_monotonic_ns >= (
        first_close.close_completed_monotonic_ns
    )


def test_camera_open_and_reopen_are_exact_identity_bound() -> None:
    identity = _camera_identity()
    provider = DeterministicFakeB0477ConnectionProvider(identity)
    wrong = replace(identity, unit_serial="SYNTHETIC-WRONG-UNIT")

    with pytest.raises(FakeConnectionBoundaryError, match="exactly match"):
        provider.discover_exact_b0477(B0477DiscoveryRequest(RUN_ID, wrong))

    discovery = provider.discover_exact_b0477(B0477DiscoveryRequest(RUN_ID, identity))
    with pytest.raises(FakeConnectionBoundaryError, match="identity mismatch"):
        provider.open_selected_b0477(
            CameraOpenRequest(RUN_ID, discovery.receipt_sha256, wrong)
        )


def test_camera_configuration_values_are_bounded_and_frozen() -> None:
    controls = B0477ManualControls(8_000, 1.0, 5_000)
    with pytest.raises(FrozenInstanceError):
        controls.exposure_us = 1  # type: ignore[misc]
    with pytest.raises(PhysicalConnectionContractError, match="exposure_us"):
        B0477ManualControls(float("nan"), 1.0, 5_000)
    with pytest.raises(PhysicalConnectionContractError, match="white_balance_kelvin"):
        B0477ManualControls(8_000, 1.0, 30_000)


def test_captured_frame_binds_exact_bytes_with_a_32_mib_ceiling() -> None:
    payload = b"synthetic-encoded-frame"
    receipt = _fresh_receipt(payload)
    frame = CapturedFrame(receipt, payload)

    assert frame.payload is payload
    assert frame.receipt.payload_sha256 == hashlib.sha256(payload).hexdigest()
    assert 5472 * 3648 * 2 > MAX_IMMUTABLE_FRAME_BYTES

    with pytest.raises(PhysicalConnectionContractError, match="length does not match"):
        CapturedFrame(receipt, payload + b"!")
    with pytest.raises(PhysicalConnectionContractError, match="receipt digest"):
        CapturedFrame(receipt, b"X" * len(payload))
    with pytest.raises(PhysicalConnectionContractError, match="payload_bytes"):
        replace(receipt, payload_bytes=MAX_IMMUTABLE_FRAME_BYTES + 1)


def test_frame_timing_defaults_to_host_bracket_and_device_timing_requires_proof() -> None:
    receipt = _fresh_receipt()
    assert receipt.timing_basis is FrameTimingBasis.HOST_BRACKET

    with pytest.raises(PhysicalConnectionContractError, match="requires a device proof"):
        replace(receipt, timing_basis=FrameTimingBasis.DEVICE_EXPOSURE)
    with pytest.raises(PhysicalConnectionContractError, match="cannot claim"):
        replace(receipt, device_exposure_proof_sha256="d" * 64)

    device_timed = replace(
        receipt,
        timing_basis=FrameTimingBasis.DEVICE_EXPOSURE,
        device_exposure_proof_sha256="d" * 64,
    )
    assert device_timed.timing_basis is FrameTimingBasis.DEVICE_EXPOSURE
    assert device_timed.device_exposure_proof_sha256 == "d" * 64


def test_unpowered_arm_discovery_proves_identity_without_open_or_io() -> None:
    identity = _arm_identity()
    provider = DeterministicFakeRoArmConnectionProvider(identity, _response())
    request = UnpoweredArmIdentityRequest(RUN_ID, identity, "4" * 64)

    receipt = provider.inspect_unpowered_usb_identity(request)

    assert isinstance(provider, FeedbackOnlyRoArmConnectionProvider)
    assert receipt.schema == ROARM_UNPOWERED_IDENTITY_RECEIPT_SCHEMA
    assert receipt.observed_identity.identity_sha256 == identity.identity_sha256
    assert receipt.serial_port_opened is False
    assert receipt.bytes_read == 0
    assert receipt.bytes_written == 0
    assert identity.port_name == "COM99"
    assert identity.persistent_port_path != identity.port_name


def test_single_feedback_receipt_retains_exact_bytes_timestamps_and_buffer_state() -> None:
    identity = _arm_identity()
    response = _response()
    provider = DeterministicFakeRoArmConnectionProvider(identity, response)
    identity_receipt = provider.inspect_unpowered_usb_identity(
        UnpoweredArmIdentityRequest(RUN_ID, identity, "4" * 64)
    )
    request = SingleT105FeedbackRequest(
        RUN_ID,
        identity_receipt.receipt_sha256,
        identity.identity_sha256,
        "5" * 64,
        "6" * 64,
        "feedback-session-001",
        3_000_100,
    )

    receipt = provider.acquire_single_t105_feedback(request)

    assert receipt.schema == ROARM_T105_RECEIPT_SCHEMA
    assert receipt.request_bytes == b'{"T":105}\n'
    assert receipt.response_bytes == response
    assert receipt.request_bytes_sha256 == hashlib.sha256(receipt.request_bytes).hexdigest()
    assert receipt.response_bytes_sha256 == hashlib.sha256(response).hexdigest()
    assert receipt.pre_request_bytes_waiting == 0
    assert receipt.post_response_bytes_waiting == 0
    assert receipt.write_attempts == 1
    assert receipt.feedback_query_count == 1
    assert receipt.retry_count == 0
    assert receipt.t104_motion_count == 0
    assert receipt.connection_closed is True
    assert list(receipt.timing.to_dict().values()) == sorted(
        receipt.timing.to_dict().values()
    )
    assert receipt.to_dict()["request_bytes_hex"] == receipt.request_bytes.hex()
    assert len(receipt.receipt_sha256) == 64


def test_t105_provider_has_no_retry_and_malformed_first_reply_consumes_attempt() -> None:
    identity = _arm_identity()
    provider = DeterministicFakeRoArmConnectionProvider(identity, b"not-json\n")
    identity_receipt = provider.inspect_unpowered_usb_identity(
        UnpoweredArmIdentityRequest(RUN_ID, identity, "4" * 64)
    )
    request = SingleT105FeedbackRequest(
        RUN_ID,
        identity_receipt.receipt_sha256,
        identity.identity_sha256,
        "5" * 64,
        "6" * 64,
        "feedback-session-001",
        3_000_100,
    )

    with pytest.raises(FakeConnectionBoundaryError, match="response is invalid"):
        provider.acquire_single_t105_feedback(request)
    with pytest.raises(FakeConnectionBoundaryError, match="retry prohibited"):
        provider.acquire_single_t105_feedback(request)


def test_t105_receipt_rejects_stale_prebuffer_and_wrong_request_bytes() -> None:
    identity = _arm_identity()
    provider = DeterministicFakeRoArmConnectionProvider(
        identity, _response(), pre_request_bytes_waiting=1
    )
    identity_receipt = provider.inspect_unpowered_usb_identity(
        UnpoweredArmIdentityRequest(RUN_ID, identity, "4" * 64)
    )
    request = SingleT105FeedbackRequest(
        RUN_ID,
        identity_receipt.receipt_sha256,
        identity.identity_sha256,
        "5" * 64,
        "6" * 64,
        "feedback-session-001",
        3_000_100,
    )
    with pytest.raises(PhysicalConnectionContractError, match="buffered bytes"):
        provider.acquire_single_t105_feedback(request)

    parsed_digest = canonical_sha256({"T": 1051})
    with pytest.raises(PhysicalConnectionContractError, match="exactly one T=105"):
        SingleT105FeedbackReceipt(
            run_id=RUN_ID,
            provider_descriptor_sha256=FAKE_PROVIDER_DESCRIPTOR.descriptor_sha256,
            request_context_sha256=request.request_context_sha256,
            arm_identity_sha256=identity.identity_sha256,
            controller_session_id=request.controller_session_id,
            timing=T105TransactionTiming(1, 2, 3, 4, 5, 6, 7),
            pre_request_bytes_waiting=0,
            post_response_bytes_waiting=0,
            request_bytes=b'{"T":104}\n',
            response_bytes=_response(),
            request_bytes_sha256=hashlib.sha256(b'{"T":104}\n').hexdigest(),
            response_bytes_sha256=hashlib.sha256(_response()).hexdigest(),
            parsed_response_sha256=parsed_digest,
            write_attempts=1,
            feedback_query_count=1,
            retry_count=0,
            t104_motion_count=0,
            connection_closed=True,
        )


def test_feedback_protocol_exposes_no_generic_send_motion_or_contact_api() -> None:
    public_methods = {
        name
        for name in dir(FeedbackOnlyRoArmConnectionProvider)
        if not name.startswith("_")
    }

    assert public_methods == {
        "acquire_single_t105_feedback",
        "descriptor",
        "inspect_unpowered_usb_identity",
    }
    for prohibited in ("send", "write", "exchange", "send_motion", "t104", "contact"):
        assert prohibited not in public_methods


def test_receipt_types_use_slots_and_reject_unknown_fields() -> None:
    identity = _arm_identity()
    receipt = UnpoweredArmIdentityReceipt(
        run_id=RUN_ID,
        provider_descriptor_sha256=FAKE_PROVIDER_DESCRIPTOR.descriptor_sha256,
        request_sha256="7" * 64,
        power_off_attestation_sha256="8" * 64,
        observed_identity=identity,
        observed_monotonic_ns=1,
        serial_port_opened=False,
        bytes_read=0,
        bytes_written=0,
    )
    # CPython's generated frozen+slots setter reports TypeError for an unknown
    # slot on some supported versions and AttributeError on others.
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        receipt.unknown_field = True  # type: ignore[attr-defined]


def test_timing_and_evidence_limits_fail_closed() -> None:
    with pytest.raises(PhysicalConnectionContractError, match="monotonically"):
        T105TransactionTiming(1, 2, 3, 9, 5, 6, 7)

    with pytest.raises(PhysicalConnectionContractError, match="four lowercase"):
        replace(_camera_identity(), vid="0x1234")
