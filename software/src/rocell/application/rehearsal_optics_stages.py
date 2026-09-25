"""Substantive, hardware-free optics checks; not stage advancement authority.

Only explicit evaluation reads fixed workspace inputs or renders synthetic
pixels. Verification reparses retained data and recomputes predicates without
filesystem, detector, camera, serial, native-provider or session I/O. A caller
must independently authenticate the expected binding and retained evidence hash.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, cast


SCHEMA = "rocell.rehearsal_optics_stage.v1"
EVALUATOR_ID = "SUBSTANTIVE_SYNTHETIC_OPTICS_V1"
MAX_EVIDENCE_BYTES = 96 * 1024
MAX_SEQUENCE = 1_000_000
_FIXTURE = "software/tests/fixtures/camera/b0477_synthetic_intrinsics_rehearsal.json"
_PROFILE = "software/config/camera_profiles/arducam_b0477_imx283_16mm.json"
_STAGES = ("optics_intrinsics", "static_registration")
_HEX = re.compile(r"[0-9a-f]{64}")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_VISION_SOURCE_KEYS = {
    "camera_profile_canonical",
    "camera_profile_file",
    "detected_batch",
    "detector_configuration",
    "detector_implementation",
    "fit_detection_batch",
    "nominal_fit_tag_map",
    "nominal_held_out_station_map",
    "nominal_intrinsics",
    "nominal_tag_map",
    "optical_contract",
    "raw_detected_batch",
    "rectified_detection_batch",
    "rectifier_configuration",
    "rectifier_implementation",
    "renderer_config",
    "renderer_definition",
    "renderer_source_bundle",
    "scene_source:config/workcell_layout.json",
    "scene_source:fiducials/apriltag_map.json",
    "support_design",
    "support_source:camera_architecture_plan",
    "support_source:purchased_camera_profile",
    "support_source:robot_reach_screening",
    "support_source:workcell_layout",
    "synthetic_undistortion_map",
}
_AUTHORITY = {
    "composition": "HARDWARE_INCAPABLE_REHEARSAL",
    "physical_authority": False,
    "hardware_accessed": False,
    "physical_calibration_valid": False,
    "stage_advance_authority": False,
    "physical_release_effect": "NONE",
}
_PROVENANCE = {
    "camera_dataset_role": "DEPENDENCY_ONLY_NOT_EVALUATED_PIXELS",
    "binding_camera_role": "SESSION_DEPENDENCY_NOT_FIXTURE_CAMERA_IDENTITY",
    "binding_settings_role": "SESSION_DEPENDENCY_NOT_FIXTURE_OPTICAL_SETTINGS",
    "intrinsics_input": "SEALED_SYNTHETIC_INTRINSICS_FIXTURE_NOT_MEASURED",
    "registration_input": "NOMINAL_STATIC_SCENE_RENDER_NOT_NATIVE_CAMERA_DATASET",
    "raw_registration_pixels_retained": False,
    "installed_optics_or_geometry_verified": False,
}


class RehearsalOpticsError(ValueError):
    """Invalid, oversized, inconsistent or untrusted-by-binding stage data."""


def _digest(value: object) -> str:
    if type(value) is not str or _HEX.fullmatch(value) is None:
        raise RehearsalOpticsError("expected a lowercase SHA-256 digest")
    return value


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise RehearsalOpticsError("expected a strict Boolean")
    return value


def _integer(value: object, maximum: int = MAX_SEQUENCE) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise RehearsalOpticsError("integer is outside its bound")
    return value


def _number(value: object) -> float:
    if type(value) not in (int, float) or not math.isfinite(cast(float, value)):
        raise RehearsalOpticsError("expected a finite number, not a Boolean")
    return value  # type: ignore[return-value]


def _numbers(value: object, count: int) -> tuple[float, ...]:
    if type(value) is not list or len(value) != count:
        raise RehearsalOpticsError("numeric vector has an invalid length")
    return tuple(_number(item) for item in value)


def _object(value: object, keys: set[str] | None = None) -> dict[str, Any]:
    if type(value) is not dict or (keys is not None and set(value) != keys):
        raise RehearsalOpticsError("object has missing or unknown fields")
    return value


def _bounded_tree(value: object, depth: int = 0) -> None:
    # Bound structure before encoding or model reconstruction. Strings include
    # the original small intrinsics fixture, preserving its exact byte hash.
    if depth > 24:
        raise RehearsalOpticsError("report nesting exceeds the bound")
    if type(value) is dict:
        if len(value) > 128 or any(type(key) is not str for key in value):
            raise RehearsalOpticsError("invalid object keys/count")
        for key, item in value.items():
            if len(key) > 256:
                raise RehearsalOpticsError("object key too long")
            _bounded_tree(item, depth + 1)
    elif type(value) is list:
        if len(value) > 128:
            raise RehearsalOpticsError("array too long")
        for item in value:
            _bounded_tree(item, depth + 1)
    elif type(value) is str:
        if len(value) > MAX_EVIDENCE_BYTES:
            raise RehearsalOpticsError("string too long")
    elif type(value) is float:
        _number(value)
    elif type(value) is int:
        if abs(value) > (1 << 63) - 1:
            raise RehearsalOpticsError("integer too large")
    elif value is not None and type(value) is not bool:
        raise RehearsalOpticsError("non-JSON value")


def _canonical(value: object) -> bytes:
    _bounded_tree(value)
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError) as error:
        raise RehearsalOpticsError("invalid JSON encoding") from error
    if len(payload) > MAX_EVIDENCE_BYTES:
        raise RehearsalOpticsError("stage evidence exceeds the 96 KiB bound")
    return payload


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _same(left: object, right: object, label: str) -> None:
    # Canonical comparison distinguishes true/1 and false/0, unlike dict ==.
    if _canonical(left) != _canonical(right):
        raise RehearsalOpticsError(f"{label} mismatch")


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RehearsalOpticsError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise RehearsalOpticsError("nonfinite JSON value")


def _decode(payload: bytes) -> dict[str, Any]:
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_EVIDENCE_BYTES:
        raise RehearsalOpticsError("evidence must be nonempty bounded bytes")
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique,
            parse_constant=_reject_constant,
        )
        _bounded_tree(value)
        return _object(value)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise RehearsalOpticsError("invalid bounded stage JSON") from error


@dataclass(frozen=True, slots=True)
class RehearsalOpticsBinding:
    workspace_source_sha256: str
    catalog_sha256: str
    cell_id: str
    session_id: str
    operator_id: str
    stage: str
    predecessor_receipt_sha256: str
    predecessor_review_sha256: str
    camera_identity_sha256: str
    settings_epoch: str
    camera_dataset_manifest_sha256: str

    def __post_init__(self) -> None:
        for key, value in asdict(self).items():
            if key in {"cell_id", "session_id", "operator_id"}:
                if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
                    raise RehearsalOpticsError(f"invalid {key}")
            elif key == "stage":
                if type(value) is not str or value not in _STAGES:
                    raise RehearsalOpticsError("unsupported optics stage")
            else:
                _digest(value)

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RehearsalOpticsEvidence:
    """Immutable canonical bytes; callers cannot mutate retained nested reports."""

    _payload: bytes

    @property
    def outcome(self) -> str:
        return self.to_dict()["outcome"]  # type: ignore[no-any-return]

    @property
    def checks(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.to_dict()["checks"])

    @property
    def evidence_sha256(self) -> str:
        return hashlib.sha256(self._payload).hexdigest()

    def canonical_bytes(self) -> bytes:
        return self._payload

    def to_dict(self) -> dict[str, Any]:
        return _decode(self._payload)


def _check(
    check_id: str, passed: bool, observed: object, meaning: str
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "passed": passed,
        "observed": observed,
        "meaning": meaning,
    }


def _intrinsics_checks(
    reports: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from rocell.calibration.static_camera_intrinsics import (
        StaticCameraIntrinsicsAssessment,
        parse_static_camera_intrinsics_json,
    )

    _object(reports, {"intrinsics"})
    report = _object(
        reports["intrinsics"],
        {
            "fixture_path",
            "fixture_utf8",
            "fixture_sha256",
            "assessment",
        },
    )
    if report["fixture_path"] != _FIXTURE or type(report["fixture_utf8"]) is not str:
        raise RehearsalOpticsError(
            "intrinsics fixture source is not the fixed synthetic input"
        )
    raw = report["fixture_utf8"].encode("utf-8")
    _same(report["fixture_sha256"], hashlib.sha256(raw).hexdigest(), "fixture hash")
    artifact = parse_static_camera_intrinsics_json(raw)
    assessment = _object(report["assessment"])
    gates = _boolean(assessment["structural_gates_passed"])
    expected = StaticCameraIntrinsicsAssessment(
        artifact.artifact_id,
        artifact.canonical_sha256,
        artifact.input_bindings_sha256,
        len(artifact.training_image_ids),
        len(artifact.held_out_image_ids),
    ).to_dict()
    # A regressed evaluator reporting failure remains a retained BLOCKED result;
    # no verifier may replace that failure with the parser's successful outcome.
    expected["structural_gates_passed"] = gates
    _same(assessment, expected, "intrinsics assessment schema/bindings")
    checks = [
        _check(
            "intrinsics_artifact_reparsed",
            True,
            artifact.canonical_sha256,
            "Full sealed synthetic fixture passed the existing strict parser; no installed solve.",
        ),
        _check(
            "intrinsics_assessor_gates",
            gates,
            gates,
            "The invoked assessor must itself report structural success.",
        ),
        _check(
            "intrinsics_partitions",
            bool(artifact.training_image_ids and artifact.held_out_image_ids),
            {
                "training": len(artifact.training_image_ids),
                "held_out": len(artifact.held_out_image_ids),
            },
            "Existing parser validates disjoint commitments, coverage and per-view residuals.",
        ),
    ]
    inputs = {
        "fixture_file_sha256": report["fixture_sha256"],
        "fixture_artifact_sha256": artifact.canonical_sha256,
        "fixture_profile_sha256": artifact.profile_source_file_sha256,
        "fixture_input_bindings_sha256": artifact.input_bindings_sha256,
        "fixture_images_manifest_sha256": artifact.images_manifest_sha256,
        "fixture_split_commitment_sha256": artifact.split_commitment_sha256,
    }
    return checks, inputs


def _vision_report(value: object) -> Any:
    """Reconstruct existing pure value models, then reject any extra field.

    Their to_dict round trip validates the complete fixed report schema,
    derived status, policy limits, authority and pixel-space hashes. This does
    not render, detect, estimate, read files or authenticate the original pixels.
    """
    from rocell.application.b0477_static_vision import (
        B0477HeldOutStationResidual,
        B0477NominalProjection,
        B0477PixelStatistics,
        B0477PoseComparison,
        B0477StaticVisionMode,
        B0477StaticVisionReport,
    )

    document = _object(value)
    p = _object(document["nominal_projection"])
    published = _object(p["published_fov_deg"])
    effective = _object(p["effective_rectilinear_fov_deg"])
    projection = B0477NominalProjection(
        optical_frame=p["optical_frame"],
        resolution_px=cast(
            tuple[int, int], tuple(_integer(v, 10000) for v in p["resolution_px"])
        ),
        intrinsics_row_major=_numbers(p["intrinsics_row_major"], 9),
        camera_T_board_row_major=_numbers(p["camera_T_board_row_major"], 16),
        camera_axis_xy_board_mm=cast(
            tuple[float, float], _numbers(p["camera_axis_xy_board_mm"], 2)
        ),
        entrance_pupil_z_board_mm=_number(p["entrance_pupil_z_board_mm"]),
        tag_plane_z_board_mm=_number(p["tag_plane_z_board_mm"]),
        nominal_working_distance_mm=_number(p["nominal_working_distance_mm"]),
        published_fov_deg=(
            _number(published["horizontal"]),
            _number(published["vertical"]),
        ),
        effective_rectilinear_fov_deg=(
            _number(effective["horizontal"]),
            _number(effective["vertical"]),
        ),
        distortion_coefficients=cast(
            tuple[float, float, float, float, float],
            _numbers(p["distortion"]["coefficients_k1_k2_p1_p2_k3"], 5),
        ),
        intrinsics_source_sha256=_digest(p["intrinsics_source_sha256"]),
        undistortion_map_sha256=_digest(p["undistortion_map_sha256"]),
        optical_contract_sha256=_digest(p["optical_contract_sha256"]),
        capture_pixel_space=p["pixel_spaces"]["capture"],
        estimator_pixel_space=p["pixel_spaces"]["pose_estimator"],
    )
    s = _object(document["pixel_statistics"])
    gray, edge = _object(s["grayscale"]), _object(s["accepted_tag_edge_px"])
    optional = lambda v: None if v is None else _number(v)
    statistics = B0477PixelStatistics(
        width_px=_integer(s["resolution_px"][0], 10000),
        height_px=_integer(s["resolution_px"][1], 10000),
        pixel_count=_integer(s["pixel_count"], 64 * 1024 * 1024),
        jpeg_byte_count=_integer(s["jpeg_byte_count"], 64 * 1024 * 1024),
        jpeg_sha256=_digest(s["jpeg_sha256"]),
        minimum_gray=_integer(gray["minimum"], 255),
        maximum_gray=_integer(gray["maximum"], 255),
        mean_gray=_number(gray["mean"]),
        dark_fraction_below_128=_number(gray["fraction_below_128"]),
        accepted_tag_edge_min_px=optional(edge["minimum"]),
        accepted_tag_edge_mean_px=optional(edge["mean"]),
        accepted_tag_edge_max_px=optional(edge["maximum"]),
    )
    c = _object(document["pose_comparison"])
    comparison = B0477PoseComparison(
        _boolean(c["estimate_available"]),
        optional(c["translation_error_mm"]),
        optional(c["rotation_error_deg"]),
        optional(c["inlier_reprojection_rmse_px"]),
    )
    registration = _object(document["board_registration"])
    residuals = tuple(
        B0477HeldOutStationResidual(
            row["station_name"],
            _integer(row["tag_id"], 5),
            _number(row["corner_rmse_px"]),
            _number(row["maximum_corner_error_px"]),
        )
        for row in registration["held_out_station_residuals"]
    )
    tags = _object(document["tag_ids"])
    sources = _object(document["source_hashes"])
    _object(
        sources,
        _VISION_SOURCE_KEYS
        | ({"pose_observation"} if comparison.estimate_available else set()),
    )
    from rocell.calibration.static_camera_intrinsics import (
        TARGET_PROFILE_ID,
        TARGET_PROFILE_SOURCE_SHA256,
    )

    _same(
        document["camera"]["profile_id"],
        TARGET_PROFILE_ID,
        "synthetic profile identity",
    )
    _same(
        sources["camera_profile_file"],
        TARGET_PROFILE_SOURCE_SHA256,
        "synthetic profile source",
    )
    for left, right in (
        (sources["camera_profile_canonical"], projection.intrinsics_source_sha256),
        (sources["optical_contract"], projection.optical_contract_sha256),
        (sources["synthetic_undistortion_map"], projection.undistortion_map_sha256),
        (sources["detected_batch"], sources["rectified_detection_batch"]),
        (sources["nominal_tag_map"], sources["nominal_fit_tag_map"]),
        (
            sources["camera_profile_file"],
            sources["support_source:purchased_camera_profile"],
        ),
        (
            sources["scene_source:config/workcell_layout.json"],
            sources["support_source:workcell_layout"],
        ),
    ):
        _same(left, right, "retained vision source link")
    report = B0477StaticVisionReport(
        sequence=_integer(document["sequence"]),
        mode=B0477StaticVisionMode(document["mode"]),
        status=document["status"],
        detail_code=document["detail_code"],
        profile_id=document["camera"]["profile_id"],
        support_design_id=document["camera"]["support_design_id"],
        source_hashes=tuple(sorted((key, _digest(v)) for key, v in sources.items())),
        nominal_projection=projection,
        visible_tag_ids=tuple(tags["visible_in_synthetic_scene"]),
        detected_tag_ids=tuple(tags["detected_from_jpeg_pixels"]),
        inlier_tag_ids=tuple(tags["planar_pose_inliers"]),
        pixel_statistics=statistics,
        pose_comparison=comparison,
        held_out_station_residuals=residuals,
    )
    _same(document, report.to_dict(), "retained vision schema/derived values")
    return report


def _registration_checks(
    reports: dict[str, Any], sequence: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from rocell.application.b0477_static_vision import B0477StaticVisionMode

    _object(reports, {"normal", "tag_loss"})
    normal = _vision_report(reports["normal"])
    loss = _vision_report(reports["tag_loss"])
    if (
        normal.mode is not B0477StaticVisionMode.NORMAL
        or loss.mode is not B0477StaticVisionMode.TAG_LOSS
    ):
        raise RehearsalOpticsError(
            "nominal and negative report roles cannot be substituted"
        )
    if normal.sequence != sequence or loss.sequence != sequence:
        raise RehearsalOpticsError("report sequence differs from the fixture selection")
    if (
        normal.profile_id != loss.profile_id
        or normal.support_design_id != loss.support_design_id
    ):
        raise RehearsalOpticsError("normal/negative camera-support identity mismatch")
    _same(
        normal.nominal_projection.to_dict(),
        loss.nominal_projection.to_dict(),
        "normal/negative projection",
    )
    # These sources vary with pixels/scenario/pose. Every other declared source
    # must agree across the two probes; scene geometry is never redefined here.
    varying = {
        "renderer_config",
        "renderer_definition",
        "detected_batch",
        "raw_detected_batch",
        "rectified_detection_batch",
        "fit_detection_batch",
        "pose_observation",
    }
    normal_sources, loss_sources = dict(normal.source_hashes), dict(loss.source_hashes)
    _same(
        {k: v for k, v in normal_sources.items() if k not in varying},
        {k: v for k, v in loss_sources.items() if k not in varying},
        "paired source inputs",
    )
    rejection = (
        loss.status == "REJECTED" and not loss.pose_comparison.estimate_available
    )
    checks = [
        _check(
            "nominal_pose_policy",
            normal.passes_nominal_policy,
            normal.pose_comparison.to_dict(),
            "Actual nominal tag/inlier/numeric policy, not process exit status.",
        ),
        _check(
            "held_out_stations",
            normal.held_out_station_checks_passed,
            [r.to_dict() for r in normal.held_out_station_residuals],
            "K0/P0 residuals checked independently; never used to fit T0-T3 pose.",
        ),
        _check(
            "tag_loss_rejected",
            rejection,
            {
                "status": loss.status,
                "estimate_available": loss.pose_comparison.estimate_available,
            },
            "Expected negative-test rejection only; cannot replace nominal readiness.",
        ),
        _check(
            "distinct_rendered_inputs",
            normal.pixel_statistics.jpeg_sha256 != loss.pixel_statistics.jpeg_sha256,
            {
                "normal": normal.pixel_statistics.jpeg_sha256,
                "tag_loss": loss.pixel_statistics.jpeg_sha256,
            },
            "Synthetic JPEG input hashes differ; no physical capture freshness claim.",
        ),
    ]
    inputs = {
        "normal_report_sha256": _hash(reports["normal"]),
        "tag_loss_report_sha256": _hash(reports["tag_loss"]),
        "normal_sources": normal_sources,
        "tag_loss_sources": loss_sources,
        "normal_jpeg_sha256": normal.pixel_statistics.jpeg_sha256,
        "tag_loss_jpeg_sha256": loss.pixel_statistics.jpeg_sha256,
    }
    return checks, inputs


def _derive(
    document: dict[str, Any], binding: RehearsalOpticsBinding
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reports = _object(document["reports"])
    if binding.stage == "optics_intrinsics":
        if document["sequence"] is not None:
            raise RehearsalOpticsError(
                "intrinsics stage does not select a pixel sequence"
            )
        return _intrinsics_checks(reports)
    return _registration_checks(reports, _integer(document["sequence"]))


def verify_rehearsal_optics_evidence(
    payload: bytes,
    *,
    expected_binding: RehearsalOpticsBinding,
    expected_evidence_sha256: str | None = None,
    expected_evaluator_source_sha256: str | None = None,
) -> RehearsalOpticsEvidence:
    """Pure strict verification; trust comes from caller-owned retained bindings.

    No pixels or file references are opened. An optional trusted whole-document
    digest detects resealing/substitution; without it this verifies consistency,
    not authenticity of arbitrary supplied report data.
    """
    if type(expected_binding) is not RehearsalOpticsBinding:
        raise RehearsalOpticsError("expected binding must be the exact typed contract")
    expected_binding.__post_init__()
    try:
        document = _decode(payload)
        _object(
            document,
            {
                "schema",
                "binding",
                "evaluator",
                "sequence",
                "provenance",
                "reports",
                "report_hashes",
                "selected_inputs",
                "selected_inputs_sha256",
                "checks",
                "outcome",
                "authority",
            },
        )
        _same(document["schema"], SCHEMA, "schema")
        _same(document["binding"], expected_binding.to_dict(), "expected binding")
        _same(document["authority"], _AUTHORITY, "zero authority")
        _same(document["provenance"], _PROVENANCE, "provenance")
        evaluator = _object(document["evaluator"], {"id", "source_file_sha256"})
        _same(evaluator["id"], EVALUATOR_ID, "evaluator identity")
        _digest(evaluator["source_file_sha256"])
        if expected_evaluator_source_sha256 is not None:
            _same(
                evaluator["source_file_sha256"],
                _digest(expected_evaluator_source_sha256),
                "evaluator source",
            )
        canonical = _canonical(document)
        if expected_evidence_sha256 is not None:
            _same(
                hashlib.sha256(canonical).hexdigest(),
                _digest(expected_evidence_sha256),
                "retained evidence hash",
            )
        _same(
            document["report_hashes"],
            {k: _hash(v) for k, v in document["reports"].items()},
            "report hashes",
        )
        checks, inputs = _derive(document, expected_binding)
        _same(document["checks"], checks, "derived checks")
        _same(document["selected_inputs"], inputs, "selected input manifest")
        _same(document["selected_inputs_sha256"], _hash(inputs), "input manifest hash")
        outcome = (
            "REHEARSAL_CHECKS_PASSED" if all(c["passed"] for c in checks) else "BLOCKED"
        )
        _same(document["outcome"], outcome, "derived stage outcome")
        return RehearsalOpticsEvidence(canonical)
    except (KeyError, IndexError, TypeError, ValueError, OverflowError) as error:
        if isinstance(error, RehearsalOpticsError):
            raise
        raise RehearsalOpticsError("retained optics report is invalid") from error


def _read_fixed(root: Path, relative: str) -> bytes:
    selected = root / relative
    for path in (selected, *selected.parents):
        if path.is_symlink() or (
            getattr(path.lstat(), "st_file_attributes", 0) & 0x400
        ):
            raise RehearsalOpticsError("fixed input has a link/reparse component")
        if path == root:
            break
    with selected.open("rb") as stream:
        payload = stream.read(MAX_EVIDENCE_BYTES + 1)
    if not 0 < len(payload) <= MAX_EVIDENCE_BYTES:
        raise RehearsalOpticsError("fixed input exceeds evidence budget")
    return payload


def evaluate_rehearsal_optics_stage(
    workspace: Path,
    binding: RehearsalOpticsBinding,
    *,
    sequence: int = 0,
) -> RehearsalOpticsEvidence:
    """Explicit no-device evaluation of fixed existing synthetic inputs.

    No provider injection, destination, raw image, native dataset or hardware
    enable flag is accepted. The caller retains and reviews this result; this
    function cannot commit a stage or issue a permit.
    """
    if type(binding) is not RehearsalOpticsBinding:
        raise RehearsalOpticsError("binding must be the exact typed contract")
    binding.__post_init__()
    _integer(sequence)
    if binding.stage == "optics_intrinsics" and sequence != 0:
        raise RehearsalOpticsError("intrinsics does not accept a sequence selection")
    source_bytes = Path(__file__).read_bytes()
    evaluator_hash = hashlib.sha256(source_bytes).hexdigest()
    root = Path(workspace).resolve(strict=True)
    if binding.stage == "optics_intrinsics":
        from rocell.calibration.static_camera_intrinsics import (
            assess_static_camera_intrinsics_rehearsal,
            parse_static_camera_intrinsics_json,
        )
        from rocell.vision.camera_profile import load_camera_profile

        raw = _read_fixed(root, _FIXTURE)
        artifact = parse_static_camera_intrinsics_json(raw)
        profile = load_camera_profile(root / _PROFILE)
        assessment = assess_static_camera_intrinsics_rehearsal(
            artifact, purchased_profile=profile
        )
        reports: dict[str, Any] = {
            "intrinsics": {
                "fixture_path": _FIXTURE,
                "fixture_utf8": raw.decode("utf-8"),
                "fixture_sha256": hashlib.sha256(raw).hexdigest(),
                "assessment": assessment.to_dict(),
            }
        }
        if _read_fixed(root, _FIXTURE) != raw:
            raise RehearsalOpticsError("fixture changed during evaluation")
    else:
        from rocell.application.b0477_static_vision import (
            B0477StaticVisionMode,
            run_b0477_static_vision_rehearsal,
        )

        reports = {
            "normal": run_b0477_static_vision_rehearsal(
                root, sequence=sequence, mode=B0477StaticVisionMode.NORMAL
            ).to_dict(),
            "tag_loss": run_b0477_static_vision_rehearsal(
                root, sequence=sequence, mode=B0477StaticVisionMode.TAG_LOSS
            ).to_dict(),
        }
    document: dict[str, Any] = {
        "schema": SCHEMA,
        "binding": binding.to_dict(),
        "evaluator": {"id": EVALUATOR_ID, "source_file_sha256": evaluator_hash},
        "sequence": sequence if binding.stage == "static_registration" else None,
        "provenance": dict(_PROVENANCE),
        "reports": reports,
        "authority": dict(_AUTHORITY),
    }
    checks, inputs = _derive(document, binding)
    document.update(
        {
            "checks": checks,
            "selected_inputs": inputs,
            "selected_inputs_sha256": _hash(inputs),
            "report_hashes": {k: _hash(v) for k, v in reports.items()},
            "outcome": (
                "REHEARSAL_CHECKS_PASSED"
                if all(c["passed"] for c in checks)
                else "BLOCKED"
            ),
        }
    )
    if Path(__file__).read_bytes() != source_bytes:
        raise RehearsalOpticsError("evaluator source changed during evaluation")
    return verify_rehearsal_optics_evidence(
        _canonical(document),
        expected_binding=binding,
        expected_evaluator_source_sha256=evaluator_hash,
    )


__all__ = [
    "SCHEMA",
    "EVALUATOR_ID",
    "MAX_EVIDENCE_BYTES",
    "MAX_SEQUENCE",
    "RehearsalOpticsError",
    "RehearsalOpticsBinding",
    "RehearsalOpticsEvidence",
    "evaluate_rehearsal_optics_stage",
    "verify_rehearsal_optics_evidence",
]
