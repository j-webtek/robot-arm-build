from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pytest

from rocell.calibration.artifacts import (
    ArtifactAssessment,
    ArtifactState,
    CalibrationArtifact,
    CalibrationResolution,
)
from rocell.calibration.eye_on_arm_commissioning import (
    EyeOnArmCommissioningContext,
    assess_eye_on_arm_commissioning,
)
from rocell.calibration.eye_on_arm_capture_bundle import (
    MAX_BUNDLE_FILE_BYTES,
    CaptureBundleSample,
    EyeOnArmCaptureBundleError,
    FeedbackWireObservation,
    NormalizedDetectionEvidence,
    assemble_eye_on_arm_capture_bundle,
    eye_on_arm_capture_bundle_from_dict,
    load_eye_on_arm_capture_bundle,
    verify_eye_on_arm_capture_bundle,
)
from rocell.calibration.eye_on_arm_dataset import (
    CarrierPoseRecord,
    EyeOnArmCameraBinding,
    EyeOnArmDataset,
    EyeOnArmSample,
    ImageRecord,
    JointStateRecord,
    SynchronizationPolicy,
    TargetPoseRecord,
)
from rocell.calibration.eye_on_arm_evidence import (
    EyeOnArmCaptureEvidence,
    EyeOnArmEvidenceError,
    JointReferenceRule,
    RawJointFeedbackEvidence,
    eye_on_arm_capture_evidence_from_dict,
    load_eye_on_arm_capture_evidence,
    verify_eye_on_arm_fk,
)
from rocell.calibration.eye_on_arm_solver import solve_eye_on_arm
from rocell.geometry.transforms import RigidTransform, Vec3
from rocell.geometry.urdf import JointPosition, UrdfModel
from rocell.vision.camera import FramePacket, TimestampQuality


SOFTWARE_ROOT = Path(__file__).resolve().parents[2]
URDF_PATH = SOFTWARE_ROOT / "models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf"
JOINTS = (
    "base_link_to_link1",
    "link1_to_link2",
    "link2_to_link3",
    "link3_to_link4",
    "link4_to_link5",
    "link5_to_gripper_link",
)
FEEDBACK = ("b", "s", "e", "t", "r", "g")


def _hash_json(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _build_offline_fixture(
    *, carrier_error_sample: int | None = None
) -> tuple[EyeOnArmDataset, EyeOnArmCaptureEvidence, RigidTransform, RigidTransform]:
    raw_model = URDF_PATH.read_bytes()
    model_hash = hashlib.sha256(raw_model).hexdigest()
    model = UrdfModel.from_xml(raw_model.decode("utf-8"), source_name=str(URDF_PATH))
    link2_T_E = RigidTransform.from_rpy_translation_mm(
        "link2",
        "E",
        translation_mm=Vec3(18.0, -9.0, 27.0),
        roll_rad=0.07,
        pitch_rad=-0.04,
        yaw_rad=0.03,
    )
    expected_extrinsic = RigidTransform.from_rpy_translation_mm(
        "E",
        "C_arm",
        translation_mm=Vec3(31.0, -10.0, 46.0),
        roll_rad=0.10,
        pitch_rad=-0.18,
        yaw_rad=0.14,
    )
    expected_world = RigidTransform.from_rpy_translation_mm(
        "Wv",
        "B",
        translation_mm=Vec3(305.0, 457.0, 21.0),
        roll_rad=-0.06,
        pitch_rad=0.04,
        yaw_rad=0.31,
    )
    samples: list[EyeOnArmSample] = []
    raw_records: list[RawJointFeedbackEvidence] = []
    for index in range(21):
        values = (
            -1.0 + 0.1 * index,
            0.68 * math.sin(0.73 * index),
            1.0 + 0.1 * math.sin(0.31 * index),
            0.4 * math.sin(0.47 * index),
            0.5 * math.cos(0.29 * index),
            0.7,
        )
        joint_state = {
            name: JointPosition.radians(value) for name, value in zip(JOINTS, values)
        }
        root_T_link2 = model.forward_kinematics(joint_state)["link2"]
        Wv_T_link2 = RigidTransform(
            "Wv", "link2", root_T_link2.rotation, root_T_link2.translation_mm
        )
        carrier = Wv_T_link2.compose(link2_T_E)
        target = (
            expected_extrinsic.inverse().compose(carrier.inverse()).compose(expected_world)
        )
        stored_carrier = carrier
        if index == carrier_error_sample:
            stored_carrier = RigidTransform(
                "Wv",
                "E",
                carrier.rotation,
                carrier.translation_mm + Vec3(1.0, 0.0, 0.0),
            )
        sample_id = f"physical_pose_{index:02d}"
        frame_time = 2_000_000_000 + index * 1_000_000_000
        joint_time = frame_time + 250_000
        samples.append(
            EyeOnArmSample(
                sample_id=sample_id,
                frame=ImageRecord(
                    sequence=index,
                    timestamp_ns=frame_time,
                    clock_id="qualified_device_clock",
                    source_sha256=hashlib.sha256(f"image:{index}".encode()).hexdigest(),
                    width_px=1920,
                    height_px=1080,
                ),
                joint_state=JointStateRecord(
                    sequence=index,
                    timestamp_ns=joint_time,
                    clock_id="qualified_device_clock",
                    settled_duration_ms=500.0,
                    positions_rad=tuple(zip(JOINTS, values)),
                ),
                carrier_pose=CarrierPoseRecord(
                    joint_sequence=index,
                    source="offline_fk",
                    transform=stored_carrier,
                ),
                target_pose=TargetPoseRecord(
                    frame_sequence=index,
                    detector="apriltag_bundle",
                    transform=target,
                    observation_count=24,
                    reprojection_rms_px=0.2,
                ),
            )
        )
        raw_fields = {
            "T": 1051,
            **{field: value for field, value in zip(FEEDBACK, values)},
            "capture_sequence": index,
        }
        raw_records.append(
            RawJointFeedbackEvidence(
                sample_id=sample_id,
                joint_sequence=index,
                timestamp_ns=joint_time,
                clock_id="qualified_device_clock",
                fields_sha256=_hash_json(raw_fields),
                fields=raw_fields,
            )
        )
    source_hashes = {
        "arm_frame_contract": "1" * 64,
        "camera_manifest": "2" * 64,
        "camera_intrinsics": "3" * 64,
        "carrier_registration": "4" * 64,
        "carrier_kinematic_model": model_hash,
        "measured_tag_map": "6" * 64,
        "robot_reference": "7" * 64,
    }
    dataset = EyeOnArmDataset(
        dataset_id="OFFLINE-FK-IMX335B-001",
        dataset_kind="OFFLINE_CAPTURE",
        camera=EyeOnArmCameraBinding(
            manufacturer="Waveshare",
            model="IMX335 5MP USB Camera (B)",
            sku="26719",
            interface="USB 2.0",
            architecture="eye_on_moving_upper_arm",
            carrier_frame="E",
            optical_frame="C_arm",
            width_px=1920,
            height_px=1080,
            pixel_format="MJPG",
            fps=30.0,
        ),
        synchronization=SynchronizationPolicy(
            mode="settled_stop_and_look",
            clock_id="qualified_device_clock",
            timestamp_basis="device_exposure",
            max_pair_delta_ns=1_000_000,
            minimum_settled_duration_ms=250.0,
        ),
        source_hashes=source_hashes,
        samples=tuple(samples),
        held_out_sample_ids=tuple(f"physical_pose_{index:02d}" for index in range(15, 21)),
    )
    rules = tuple(
        JointReferenceRule(joint, field, 1, 0.0)
        for joint, field in zip(JOINTS, FEEDBACK)
    )
    evidence = EyeOnArmCaptureEvidence(
        evidence_id="OFFLINE-FK-EVIDENCE-001",
        dataset_id=dataset.dataset_id,
        dataset_sha256=dataset.content_hash,
        manifest_id="TEST-MANIFEST-001",
        active_build_id="TEST-BUILD-001",
        camera_usb_identity_sha256="8" * 64,
        camera_settings_sha256="9" * 64,
        timing_qualification_sha256="a" * 64,
        kinematic_model_sha256=model_hash,
        carrier_registration_sha256="4" * 64,
        robot_reference_sha256="7" * 64,
        link2_T_E=link2_T_E,
        joint_reference=rules,
        raw_joint_feedback=tuple(raw_records),
    )
    return dataset, evidence, expected_extrinsic, expected_world


def _fixture_jpeg(width: int, height: int, index: int) -> bytes:
    """Small structurally valid JPEG with a unique bounded APP payload."""

    app_payload = f"capture-{index}".encode("ascii")
    app = b"\xff\xe0" + (len(app_payload) + 2).to_bytes(2, "big") + app_payload
    sof_payload = b"\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x01"
    sof = b"\xff\xc0" + (len(sof_payload) + 2).to_bytes(2, "big") + sof_payload
    return b"\xff\xd8" + app + sof + b"\xff\xda\x00\x02\xff\xd9"


def _wire_bytes(fields: dict[str, Any]) -> bytes:
    return (
        json.dumps(fields, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _wire_observation(
    *,
    sample_id: str,
    record_id: str,
    request_sequence: int,
    fields: dict[str, Any],
    host_base_ns: int,
    correlated_timestamp_ns: int,
    clock_id: str,
    correlation_hash: str,
) -> FeedbackWireObservation:
    wire = _wire_bytes(fields)
    return FeedbackWireObservation(
        sample_id=sample_id,
        record_id=record_id,
        request_sequence=request_sequence,
        host_request_ns=host_base_ns,
        host_first_byte_ns=host_base_ns + 10,
        host_complete_ns=host_base_ns + 20,
        host_clock_id="host_monotonic",
        correlated_capture_timestamp_ns=correlated_timestamp_ns,
        capture_clock_id=clock_id,
        clock_correlation_sha256=correlation_hash,
        wire_sha256=hashlib.sha256(wire).hexdigest(),
        decoded_fields_sha256=_hash_json(fields),
        wire_bytes=wire,
    )


def _build_capture_bundle_fixture() -> tuple[
    EyeOnArmDataset,
    EyeOnArmCaptureEvidence,
    tuple[CaptureBundleSample, ...],
]:
    dataset, evidence, _, _ = _build_offline_fixture()
    jpeg_by_id: dict[str, bytes] = {}
    rebuilt_samples: list[EyeOnArmSample] = []
    for index, sample in enumerate(dataset.samples):
        jpeg = _fixture_jpeg(sample.frame.width_px, sample.frame.height_px, index)
        jpeg_by_id[sample.sample_id] = jpeg
        rebuilt_samples.append(
            replace(
                sample,
                frame=replace(
                    sample.frame,
                    source_sha256=hashlib.sha256(jpeg).hexdigest(),
                ),
            )
        )
    dataset = replace(dataset, samples=tuple(rebuilt_samples))
    evidence = replace(evidence, dataset_sha256=dataset.content_hash)
    representative = {
        record.sample_id: record for record in evidence.raw_joint_feedback
    }
    correlation_hash = evidence.timing_qualification_sha256
    samples: list[CaptureBundleSample] = []
    for index, sample in enumerate(dataset.samples):
        stored = representative[sample.sample_id]
        fields = dict(stored.fields)
        frame_host_base = 10_000_000 + index * 1_000
        pre = _wire_observation(
            sample_id=sample.sample_id,
            record_id=f"{sample.sample_id}.pre",
            request_sequence=index * 2,
            fields=fields,
            host_base_ns=frame_host_base,
            correlated_timestamp_ns=sample.frame.timestamp_ns - 250_000,
            clock_id=sample.frame.clock_id,
            correlation_hash=correlation_hash,
        )
        post = _wire_observation(
            sample_id=sample.sample_id,
            record_id=f"{sample.sample_id}.post",
            request_sequence=index * 2 + 1,
            fields=fields,
            host_base_ns=frame_host_base + 60,
            correlated_timestamp_ns=stored.timestamp_ns,
            clock_id=stored.clock_id,
            correlation_hash=correlation_hash,
        )
        jpeg = jpeg_by_id[sample.sample_id]
        frame = FramePacket(
            capture_id=sample.sample_id,
            jpeg_bytes=jpeg,
            width_px=sample.frame.width_px,
            height_px=sample.frame.height_px,
            source_sequence=sample.frame.sequence,
            source_timestamp_ns=sample.frame.timestamp_ns,
            source_clock=sample.frame.clock_id,
            host_request_ns=frame_host_base + 30,
            host_first_byte_ns=frame_host_base + 40,
            host_complete_ns=frame_host_base + 50,
            settings_hash=evidence.camera_settings_sha256,
            timestamp_quality=TimestampQuality.DEVICE_EXPOSURE,
            freshness_token=f"frame-{index}",
            freshness_basis="device_sequence",
        )
        detection_bytes = json.dumps(
            sample.target_pose.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        detection = NormalizedDetectionEvidence(
            detector_version="apriltag-test-normalizer-1",
            input_image_sha256=frame.sha256,
            camera_intrinsics_sha256=dataset.source_hashes["camera_intrinsics"],
            tag_map_sha256=dataset.source_hashes["measured_tag_map"],
            normalized_json_sha256=hashlib.sha256(detection_bytes).hexdigest(),
            normalized_json_bytes=detection_bytes,
        )
        samples.append(
            CaptureBundleSample(
                sample_id=sample.sample_id,
                frame=frame,
                frame_host_clock_id="host_monotonic",
                exposure_start_ns=sample.frame.timestamp_ns - 100_000,
                exposure_end_ns=sample.frame.timestamp_ns + 100_000,
                exposure_clock_id=sample.frame.clock_id,
                clock_correlation_sha256=correlation_hash,
                pre_feedback=pre,
                post_feedback=post,
                representative_phase="POST",
                detection=detection,
            )
        )
    return dataset, evidence, tuple(samples)


def test_pinned_fk_recomputes_every_carrier_pose_from_raw_feedback() -> None:
    dataset, evidence, expected_extrinsic, expected_world = _build_offline_fixture()
    verification = verify_eye_on_arm_fk(dataset, evidence, URDF_PATH)
    assert verification.all_passed
    assert len(verification.samples) == 21
    assert verification.physical_release_effect == "NONE"
    assert all(sample.maximum_joint_projection_error_rad == 0.0 for sample in verification.samples)
    assert all(sample.carrier_translation_error_mm < 1e-10 for sample in verification.samples)

    result = solve_eye_on_arm(dataset)
    assert result.diagnostic_pass
    assert result.E_T_C_arm_candidate.almost_equal(
        expected_extrinsic, absolute_tolerance=1e-7
    )
    assert result.Wv_T_B_candidate.almost_equal(expected_world, absolute_tolerance=1e-7)


def test_fk_verification_reports_stored_carrier_and_raw_projection_mismatch() -> None:
    dataset, evidence, _, _ = _build_offline_fixture(carrier_error_sample=0)
    verification = verify_eye_on_arm_fk(dataset, evidence, URDF_PATH)
    assert not verification.all_passed
    assert verification.samples[0].reasons == ("CARRIER_TRANSLATION_MISMATCH",)

    dataset, evidence, _, _ = _build_offline_fixture()
    first = evidence.raw_joint_feedback[0]
    changed_fields = dict(first.fields)
    changed_fields["b"] += 0.02
    changed_record = replace(
        first,
        fields=changed_fields,
        fields_sha256=_hash_json(changed_fields),
    )
    changed_evidence = replace(
        evidence,
        raw_joint_feedback=(changed_record, *evidence.raw_joint_feedback[1:]),
    )
    verification = verify_eye_on_arm_fk(dataset, changed_evidence, URDF_PATH)
    assert not verification.all_passed
    assert "JOINT_PROJECTION_MISMATCH" in verification.samples[0].reasons
    assert "CARRIER_TRANSLATION_MISMATCH" in verification.samples[0].reasons


def test_fk_verification_rejects_wrong_model_and_evidence_bindings(tmp_path: Path) -> None:
    dataset, evidence, _, _ = _build_offline_fixture()
    wrong_model = tmp_path / "model.urdf"
    wrong_model.write_bytes(URDF_PATH.read_bytes() + b"\n")
    with pytest.raises(EyeOnArmEvidenceError, match="model hash mismatch"):
        verify_eye_on_arm_fk(dataset, evidence, wrong_model)
    with pytest.raises(EyeOnArmEvidenceError, match="different dataset"):
        verify_eye_on_arm_fk(
            dataset,
            replace(evidence, dataset_sha256="f" * 64),
            URDF_PATH,
        )

    # Colluding claims cannot nominate a changed URDF.  Even when the dataset
    # and evidence both contain the changed digest, only the reviewed model is
    # eligible for this verifier.
    changed_bytes = URDF_PATH.read_bytes().replace(
        b'<origin xyz="0 0 0" rpy="0 0 0"/>',
        b'<origin xyz="0.001 0 0" rpy="0 0 0"/>',
        1,
    )
    assert changed_bytes != URDF_PATH.read_bytes()
    changed_model = tmp_path / "colluding-model.urdf"
    changed_model.write_bytes(changed_bytes)
    changed_hash = hashlib.sha256(changed_bytes).hexdigest()
    colluding_dataset = replace(
        dataset,
        source_hashes={
            **dataset.source_hashes,
            "carrier_kinematic_model": changed_hash,
        },
    )
    colluding_evidence = replace(
        evidence,
        dataset_sha256=colluding_dataset.content_hash,
        kinematic_model_sha256=changed_hash,
    )
    with pytest.raises(EyeOnArmEvidenceError, match="not the reviewed"):
        verify_eye_on_arm_fk(colluding_dataset, colluding_evidence, changed_model)


def test_fk_report_models_reject_nonfinite_and_inconsistent_claims() -> None:
    dataset, evidence, _, _ = _build_offline_fixture()
    verification = verify_eye_on_arm_fk(dataset, evidence, URDF_PATH)
    sample = verification.samples[0]
    with pytest.raises(EyeOnArmEvidenceError, match="must be finite"):
        replace(sample, carrier_translation_error_mm=float("nan"))
    with pytest.raises(EyeOnArmEvidenceError, match="passes exactly"):
        replace(sample, reasons=("FORGED_FAILURE",))
    with pytest.raises(EyeOnArmEvidenceError, match="sample ids must be unique"):
        replace(verification, samples=(sample, sample))

    forged_sample = replace(
        sample,
        carrier_translation_error_mm=1_000_000.0,
        carrier_rotation_error_rad=1_000_000.0,
    )
    with pytest.raises(EyeOnArmEvidenceError, match="serialized policy"):
        replace(
            verification,
            samples=(forged_sample, *verification.samples[1:]),
        )


def test_capture_evidence_caps_raw_feedback_before_indexing() -> None:
    dataset, evidence, _, _ = _build_offline_fixture()
    extra = replace(
        evidence.raw_joint_feedback[-1],
        sample_id="unexpected_extra_record",
    )
    with pytest.raises(EyeOnArmEvidenceError, match="record count differs"):
        verify_eye_on_arm_fk(
            dataset,
            replace(
                evidence,
                raw_joint_feedback=(*evidence.raw_joint_feedback, extra),
            ),
            URDF_PATH,
        )

    oversized = tuple(
        replace(
            evidence.raw_joint_feedback[0],
            sample_id=f"oversized_{index:03d}",
        )
        for index in range(129)
    )
    with pytest.raises(EyeOnArmEvidenceError, match="exceeds 128"):
        replace(evidence, raw_joint_feedback=oversized)


def test_capture_evidence_round_trip_loader_and_raw_immutability(tmp_path: Path) -> None:
    _, evidence, _, _ = _build_offline_fixture()
    reloaded = eye_on_arm_capture_evidence_from_dict(evidence.to_dict())
    assert reloaded == evidence
    assert reloaded.content_hash == evidence.content_hash
    with pytest.raises(TypeError):
        reloaded.raw_joint_feedback[0].fields["b"] = 2.0  # type: ignore[index]

    path = tmp_path / "capture-evidence.json"
    payload = (json.dumps(evidence.to_dict(), sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(payload)
    loaded = load_eye_on_arm_capture_evidence(
        path, expected_file_sha256=hashlib.sha256(payload).hexdigest()
    )
    assert loaded.content_hash == evidence.content_hash


def _prerequisites(
    dataset: EyeOnArmDataset,
    evidence: EyeOnArmCaptureEvidence,
) -> CalibrationResolution:
    expected_hashes = {
        "camera_intrinsics": dataset.source_hashes["camera_intrinsics"],
        "measured_tag_map": dataset.source_hashes["measured_tag_map"],
        "robot_reference": evidence.robot_reference_sha256,
        "carrier_registration": evidence.carrier_registration_sha256,
        "carrier_kinematic_model": evidence.kinematic_model_sha256,
        "camera_physical_identity": evidence.camera_usb_identity_sha256,
        "camera_settings": evidence.camera_settings_sha256,
        "timing_qualification": evidence.timing_qualification_sha256,
    }
    return CalibrationResolution(
        {
            artifact_id: ArtifactAssessment(
                artifact_id=artifact_id,
                state=ArtifactState.VALID,
                artifact_hash=artifact_hash,
                reasons=(),
            )
            for artifact_id, artifact_hash in expected_hashes.items()
        }
    )


def test_commissioning_boundary_requires_complete_independent_evidence() -> None:
    dataset, evidence, _, _ = _build_offline_fixture()
    verification = verify_eye_on_arm_fk(dataset, evidence, URDF_PATH)
    result = solve_eye_on_arm(dataset)
    context = EyeOnArmCommissioningContext(
        manifest_id=evidence.manifest_id,
        active_build_id=evidence.active_build_id,
        source_hashes=dataset.source_hashes,
    )
    blocked = assess_eye_on_arm_commissioning(
        dataset,
        evidence,
        verification,
        result,
        _prerequisites(dataset, evidence),
        None,
        context,
    )
    assert not blocked.evidence_gate_passed
    assert any(
        check.check_id == "registry_backed_independent_validation"
        and not check.passed
        for check in blocked.checks
    )
    assert blocked.physical_release_effect == "NONE"

    independent = CalibrationArtifact(
        artifact_id="eye_on_arm_independent_validation",
        version=1,
        state=ArtifactState.VALID,
        created_utc="2026-09-01T12:00:00Z",
        manifest_id=context.manifest_id,
        active_build_id=context.active_build_id,
        dependency_hashes={
            "eye_on_arm_capture_evidence": evidence.content_hash,
            "eye_on_arm_fk_verification": verification.report_hash,
            "eye_on_arm_solver_report": result.report_hash,
        },
        parent_artifact_hashes={},
        payload={"scope": "synthetic commissioning-boundary unit fixture"},
    )
    complete = assess_eye_on_arm_commissioning(
        dataset,
        evidence,
        verification,
        result,
        _prerequisites(dataset, evidence),
        independent,
        context,
    )
    assert not complete.evidence_gate_passed
    assert complete.status == "EVIDENCE_GATE_BLOCKED"
    failed = {check.check_id for check in complete.checks if not check.passed}
    assert "registry_backed_independent_validation" in failed
    assert "qualified_pre_exposure_post_feedback_bracket" in failed
    assert "raw_wire_image_detection_bundle" in failed
    assert complete.to_dict()["authority"] == {
        "artifact_created": False,
        "artifact_installed": False,
        "motion_authorized": False,
        "contact_authorized": False,
    }


def test_commissioning_boundary_rejects_context_and_prerequisite_drift() -> None:
    dataset, evidence, _, _ = _build_offline_fixture()
    verification = verify_eye_on_arm_fk(dataset, evidence, URDF_PATH)
    result = solve_eye_on_arm(dataset)
    stale_context = EyeOnArmCommissioningContext(
        manifest_id="OTHER-MANIFEST",
        active_build_id=evidence.active_build_id,
        source_hashes={**dataset.source_hashes, "camera_manifest": "f" * 64},
    )
    resolution = CalibrationResolution(
        {
            "camera_intrinsics": ArtifactAssessment(
                "camera_intrinsics", ArtifactState.MISSING, None, ("MISSING",)
            )
        }
    )
    assessment = assess_eye_on_arm_commissioning(
        dataset,
        evidence,
        verification,
        result,
        resolution,
        None,
        stale_context,
    )
    failed = {check.check_id for check in assessment.checks if not check.passed}
    assert "claimed_manifest_build_binding" in failed
    assert "claimed_source_hashes" in failed
    assert "calibration_prerequisites_exact" in failed
    assert assessment.status == "EVIDENCE_GATE_BLOCKED"


def test_commissioning_detects_forged_report_coverage_and_prerequisite_hashes() -> None:
    dataset, evidence, _, _ = _build_offline_fixture()
    verification = verify_eye_on_arm_fk(dataset, evidence, URDF_PATH)
    result = solve_eye_on_arm(dataset)
    context = EyeOnArmCommissioningContext(
        manifest_id=evidence.manifest_id,
        active_build_id=evidence.active_build_id,
        source_hashes=dataset.source_hashes,
    )
    truncated_verification = replace(
        verification,
        samples=verification.samples[:-1],
    )
    forged_result = replace(
        result,
        residuals=result.residuals[:-1],
        source_hashes={**result.source_hashes, "camera_intrinsics": "f" * 64},
    )
    prerequisites = _prerequisites(dataset, evidence)
    wrong_camera = prerequisites.assessments["camera_intrinsics"]
    wrong_prerequisites = CalibrationResolution(
        {
            **prerequisites.assessments,
            "camera_intrinsics": replace(wrong_camera, artifact_hash="e" * 64),
        }
    )
    assessment = assess_eye_on_arm_commissioning(
        dataset,
        evidence,
        truncated_verification,
        forged_result,
        wrong_prerequisites,
        None,
        context,
    )
    failed = {check.check_id for check in assessment.checks if not check.passed}
    assert "fk_sample_coverage_exact" in failed
    assert "solver_source_hashes_exact" in failed
    assert "solver_residual_coverage_exact" in failed
    assert "solver_report_reproduced" in failed
    assert "calibration_prerequisite_hash_binding" in failed

    nonfinite_result = replace(
        result,
        held_out_summary=replace(
            result.held_out_summary,
            rms_translation_mm=float("nan"),
        ),
    )
    nonfinite = assess_eye_on_arm_commissioning(
        dataset,
        evidence,
        verification,
        nonfinite_result,
        prerequisites,
        None,
        context,
    )
    failed = {check.check_id for check in nonfinite.checks if not check.passed}
    assert "held_out_rms_translation_mm" in failed
    assert "solver_report_reproduced" in failed


def test_capture_bundle_round_trip_and_structural_verification(tmp_path: Path) -> None:
    dataset, evidence, captures = _build_capture_bundle_fixture()
    bundle = assemble_eye_on_arm_capture_bundle(
        "OFFLINE-BYTE-BUNDLE-001", dataset, evidence, captures
    )
    report = verify_eye_on_arm_capture_bundle(dataset, evidence, bundle)
    assert report.status == "STRUCTURAL_PASS_NO_PHYSICAL_AUTHORITY"
    assert report.structural_passed
    assert all(sample.passed for sample in report.samples)
    assert report.physical_release_effect == "NONE"
    assert report.to_dict()["authority"] == {
        "eligible_for_commissioning": False,
        "artifact_created": False,
        "artifact_installed": False,
        "motion_authorized": False,
        "contact_authorized": False,
    }
    assert "T1051_DEVICE_MEASUREMENT_TIMESTAMP_NOT_ON_WIRE" in report.blockers
    with pytest.raises(TypeError):
        bundle.samples[0].pre_feedback.decoded_fields["b"] = 99.0  # type: ignore[index]
    threshold_forgery = replace(
        report.samples[0],
        maximum_joint_drift_rad=1.0,
    )
    with pytest.raises(EyeOnArmCaptureBundleError, match="bundle policy"):
        replace(report, samples=(threshold_forgery, *report.samples[1:]))
    with pytest.raises(EyeOnArmCaptureBundleError, match="cannot be weakened"):
        replace(report, blockers=("NO_COMMISSIONING_AUTHORITY",))
    assert eye_on_arm_capture_bundle_from_dict(bundle.to_dict()) == bundle

    path = tmp_path / "capture-bundle.json"
    payload = json.dumps(bundle.to_dict(), sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    path.write_bytes(payload)
    loaded = load_eye_on_arm_capture_bundle(
        path,
        expected_file_sha256=hashlib.sha256(payload).hexdigest(),
    )
    assert loaded.content_hash == bundle.content_hash


def test_capture_bundle_rejects_wire_tamper_duplicates_and_parser_drift() -> None:
    _, _, captures = _build_capture_bundle_fixture()
    pre = captures[0].pre_feedback
    with pytest.raises(EyeOnArmCaptureBundleError, match="wire-byte hash mismatch"):
        replace(pre, wire_bytes=pre.wire_bytes.replace(b'"T":1051', b'"T":1052'))

    duplicate = b'{"T":1051,"T":1051,"b":0,"s":0,"e":0,"t":0,"r":0,"g":0}\n'
    with pytest.raises(EyeOnArmCaptureBundleError, match="Duplicate JSON field"):
        replace(
            pre,
            wire_bytes=duplicate,
            wire_sha256=hashlib.sha256(duplicate).hexdigest(),
            decoded_fields_sha256="0" * 64,
        )
    with pytest.raises(EyeOnArmCaptureBundleError, match="Unsupported feedback parser"):
        replace(pre, parser_id="future.parser.v2")
    with pytest.raises(EyeOnArmCaptureBundleError, match="wire line exceeds"):
        replace(
            pre,
            wire_bytes=pre.wire_bytes + b" " * (64 * 1024),
            wire_sha256=hashlib.sha256(
                pre.wire_bytes + b" " * (64 * 1024)
            ).hexdigest(),
        )


def test_capture_bundle_loader_rejects_oversized_file_before_json(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized-capture-bundle.json"
    with oversized.open("wb") as stream:
        stream.seek(MAX_BUNDLE_FILE_BYTES)
        stream.write(b"x")
    with pytest.raises(EyeOnArmCaptureBundleError, match="file exceeds size limit"):
        load_eye_on_arm_capture_bundle(oversized)


def test_capture_bundle_enforces_pre_exposure_post_semantics() -> None:
    dataset, evidence, captures = _build_capture_bundle_fixture()
    first = captures[0]
    with pytest.raises(EyeOnArmCaptureBundleError, match="do not bracket exposure"):
        replace(
            first,
            pre_feedback=replace(
                first.pre_feedback,
                correlated_capture_timestamp_ns=first.exposure_start_ns + 1,
            ),
        )
    with pytest.raises(EyeOnArmCaptureBundleError, match="sample ids differ"):
        replace(
            first,
            pre_feedback=replace(first.pre_feedback, sample_id="different_sample"),
        )
    with pytest.raises(EyeOnArmCaptureBundleError, match="host capture transaction"):
        replace(
            first,
            post_feedback=replace(
                first.post_feedback,
                host_request_ns=first.frame.host_complete_ns - 1,
                host_first_byte_ns=first.frame.host_complete_ns,
                host_complete_ns=first.frame.host_complete_ns + 1,
            ),
        )
    duplicate_sequence = replace(
        captures[1],
        pre_feedback=replace(
            captures[1].pre_feedback,
            request_sequence=captures[0].post_feedback.request_sequence,
        ),
    )
    with pytest.raises(EyeOnArmCaptureBundleError, match="globally strict"):
        assemble_eye_on_arm_capture_bundle(
            "BAD-SEQUENCE-BUNDLE",
            dataset,
            evidence,
            (captures[0], duplicate_sequence, *captures[2:]),
        )

    second = captures[1]
    regressed_time = 1_500_000_000
    regressed_second = replace(
        second,
        frame=replace(second.frame, source_timestamp_ns=regressed_time),
        exposure_start_ns=regressed_time - 100_000,
        exposure_end_ns=regressed_time + 100_000,
        pre_feedback=replace(
            second.pre_feedback,
            correlated_capture_timestamp_ns=regressed_time - 250_000,
        ),
        post_feedback=replace(
            second.post_feedback,
            correlated_capture_timestamp_ns=regressed_time + 250_000,
        ),
    )
    with pytest.raises(EyeOnArmCaptureBundleError, match="globally increasing"):
        assemble_eye_on_arm_capture_bundle(
            "REGRESSED-CLOCK-BUNDLE",
            dataset,
            evidence,
            (captures[0], regressed_second, *captures[2:]),
        )

    wrong_correlation = "c" * 64
    changed_correlations = tuple(
        replace(
            capture,
            clock_correlation_sha256=wrong_correlation,
            pre_feedback=replace(
                capture.pre_feedback,
                clock_correlation_sha256=wrong_correlation,
            ),
            post_feedback=replace(
                capture.post_feedback,
                clock_correlation_sha256=wrong_correlation,
            ),
        )
        for capture in captures
    )
    wrong_correlation_bundle = assemble_eye_on_arm_capture_bundle(
        "WRONG-CORRELATION-BUNDLE",
        dataset,
        evidence,
        changed_correlations,
    )
    with pytest.raises(EyeOnArmCaptureBundleError, match="Timing-correlation hash differs"):
        verify_eye_on_arm_capture_bundle(
            dataset,
            evidence,
            wrong_correlation_bundle,
        )


def test_capture_bundle_reports_joint_drift_but_retains_zero_authority() -> None:
    dataset, evidence, captures = _build_capture_bundle_fixture()
    first = captures[0]
    changed_fields = dict(first.pre_feedback.decoded_fields)
    changed_fields["b"] += 0.01
    changed_pre = _wire_observation(
        sample_id=first.sample_id,
        record_id=first.pre_feedback.record_id,
        request_sequence=first.pre_feedback.request_sequence,
        fields=changed_fields,
        host_base_ns=first.pre_feedback.host_request_ns,
        correlated_timestamp_ns=first.pre_feedback.correlated_capture_timestamp_ns,
        clock_id=first.pre_feedback.capture_clock_id,
        correlation_hash=first.pre_feedback.clock_correlation_sha256,
    )
    changed_capture = replace(first, pre_feedback=changed_pre)
    bundle = assemble_eye_on_arm_capture_bundle(
        "DRIFT-BUNDLE",
        dataset,
        evidence,
        (changed_capture, *captures[1:]),
    )
    report = verify_eye_on_arm_capture_bundle(dataset, evidence, bundle)
    assert report.status == "STRUCTURAL_FAIL_NO_PHYSICAL_AUTHORITY"
    assert not report.structural_passed
    assert report.samples[0].reasons == (
        "JOINT_DRIFT_EXCEEDED",
        "JOINT_RECORD_MISMATCH",
    )
    assert report.to_dict()["authority"]["eligible_for_commissioning"] is False


def test_capture_bundle_rejects_image_detection_and_representative_drift() -> None:
    dataset, evidence, captures = _build_capture_bundle_fixture()
    bundle = assemble_eye_on_arm_capture_bundle(
        "BINDING-BUNDLE", dataset, evidence, captures
    )
    first = captures[0]
    changed_jpeg = _fixture_jpeg(first.frame.width_px, first.frame.height_px, 999)
    changed_frame = replace(first.frame, jpeg_bytes=changed_jpeg)
    changed_image_bundle = replace(
        bundle,
        samples=(replace(first, frame=changed_frame), *captures[1:]),
    )
    with pytest.raises(EyeOnArmCaptureBundleError, match="Frame bytes/metadata differ"):
        verify_eye_on_arm_capture_bundle(dataset, evidence, changed_image_bundle)

    detection_document = json.loads(first.detection.normalized_json_bytes)
    detection_document["reprojection_rms_px"] = 9.0
    detection_bytes = json.dumps(
        detection_document, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    changed_detection = replace(
        first.detection,
        normalized_json_bytes=detection_bytes,
        normalized_json_sha256=hashlib.sha256(detection_bytes).hexdigest(),
    )
    changed_detection_bundle = replace(
        bundle,
        samples=(replace(first, detection=changed_detection), *captures[1:]),
    )
    with pytest.raises(EyeOnArmCaptureBundleError, match="Normalized detection differs"):
        verify_eye_on_arm_capture_bundle(dataset, evidence, changed_detection_bundle)

    wrong_intrinsics_bundle = replace(
        bundle,
        samples=(
            replace(
                first,
                detection=replace(
                    first.detection,
                    camera_intrinsics_sha256="f" * 64,
                ),
            ),
            *captures[1:],
        ),
    )
    with pytest.raises(EyeOnArmCaptureBundleError, match="camera-intrinsics"):
        verify_eye_on_arm_capture_bundle(dataset, evidence, wrong_intrinsics_bundle)

    forged_fields = dict(first.post_feedback.decoded_fields)
    forged_fields["capture_sequence"] = 999
    forged_post = _wire_observation(
        sample_id=first.sample_id,
        record_id=first.post_feedback.record_id,
        request_sequence=first.post_feedback.request_sequence,
        fields=forged_fields,
        host_base_ns=first.post_feedback.host_request_ns,
        correlated_timestamp_ns=first.post_feedback.correlated_capture_timestamp_ns,
        clock_id=first.post_feedback.capture_clock_id,
        correlation_hash=first.post_feedback.clock_correlation_sha256,
    )
    forged_bundle = replace(
        bundle,
        samples=(replace(first, post_feedback=forged_post), *captures[1:]),
    )
    with pytest.raises(EyeOnArmCaptureBundleError, match="Representative raw feedback differs"):
        verify_eye_on_arm_capture_bundle(dataset, evidence, forged_bundle)
