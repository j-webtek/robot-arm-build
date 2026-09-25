"""Bounded 3-D correspondence fitting; candidates have no physical authority.

Only the explicit fit call lazily imports NumPy. Training points determine the
proper rotation/translation; held-out points never enter centroids or SVD. A
small retained SVD certificate lets pure verification check the decomposition,
optimum and residuals without importing NumPy or running the fitter again.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import importlib
import json
import math
import re
from typing import Any, NoReturn

from rocell.geometry.transforms import RigidTransform, Rotation3, Vec3
from rocell.models.frames import Point3Mm


SCHEMA = "rocell.rigid_correspondence_result.v1"
MAX_POINTS = 128
MAX_COORDINATE_MM = 1_000_000.0
MAX_EVIDENCE_BYTES = 262_144
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
_CERTIFICATE_FIELDS = {
    "source_singular_values_mm",
    "target_singular_values_mm",
    "cross_singular_values_mm2",
    "source_right_basis",
    "target_right_basis",
    "cross_left_basis",
    "cross_right_basis",
}


class RigidCorrespondenceError(ValueError):
    """Malformed input or an unobservable correspondence system."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class RigidCorrespondenceUnavailable(RuntimeError):
    """Optional numerical dependency cannot be loaded; no fallback fit occurs."""


class CorrespondenceOrigin(str, Enum):
    SYNTHETIC_REHEARSAL_ONLY = "SYNTHETIC_REHEARSAL_ONLY"
    UNVERIFIED_SUPPLIED_OBSERVATIONS = "UNVERIFIED_SUPPLIED_OBSERVATIONS"


def _fail(code: str, message: str) -> NoReturn:
    raise RigidCorrespondenceError(code, message)


def _identifier(value: object) -> str:
    if type(value) is not str or not _ID.fullmatch(value):
        _fail("INVALID_IDENTIFIER", "IDs and frames must be exact bounded identifiers")
    return str(value)


def _digest(value: object) -> str:
    if type(value) is not str or not _HASH.fullmatch(value) or value == "0" * 64:
        _fail("INVALID_DIGEST", "An exact nonzero SHA-256 digest is required")
    return str(value)


def _number(value: object, maximum: float = 1e15) -> float:
    if type(value) not in (int, float):
        _fail("INVALID_NUMBER", "A finite bounded numeric value is required")
    try:
        result = float(value)  # type: ignore[arg-type]
    except (OverflowError, ValueError) as exc:
        raise RigidCorrespondenceError(
            "INVALID_NUMBER", "Numeric value cannot be represented within the bound"
        ) from exc
    if not math.isfinite(result) or abs(result) > maximum:
        _fail("INVALID_NUMBER", "Numeric value is nonfinite or outside its bound")
    return result


def _canonical(value: object) -> bytes:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")
    if len(encoded) > MAX_EVIDENCE_BYTES:
        _fail("EVIDENCE_TOO_LARGE", "Complete evidence exceeds its fixed byte limit")
    return encoded


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _point(point: Point3Mm) -> dict[str, Any]:
    return {"frame": point.frame, "xyz_mm": [point.x, point.y, point.z]}


@dataclass(frozen=True, slots=True)
class RigidPointPair:
    pair_id: str
    source: Point3Mm
    target: Point3Mm

    def __post_init__(self) -> None:
        _identifier(self.pair_id)
        for point in (self.source, self.target):
            if type(point) is not Point3Mm:
                _fail("INVALID_POINT", "Correspondences require exact Point3Mm values")
            _identifier(point.frame)
            for value in (point.x, point.y, point.z):
                _number(value, MAX_COORDINATE_MM)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "source": _point(self.source),
            "target": _point(self.target),
        }


@dataclass(frozen=True, slots=True)
class RigidCorrespondenceInput:
    dataset_id: str
    source_frame: str
    target_frame: str
    training: tuple[RigidPointPair, ...]
    held_out: tuple[RigidPointPair, ...]
    workspace_source_sha256: str
    binding_sha256: str
    origin: CorrespondenceOrigin
    units: str = "mm"

    def __post_init__(self) -> None:
        for value in (self.dataset_id, self.source_frame, self.target_frame):
            _identifier(value)
        if self.source_frame == self.target_frame or self.units != "mm":
            _fail(
                "FRAME_OR_UNIT_MISMATCH",
                "Distinct declared frames and millimetres are required",
            )
        if type(self.units) is not str or type(self.origin) is not CorrespondenceOrigin:
            _fail(
                "INVALID_PROVENANCE",
                "Units and origin must use the exact typed contract",
            )
        _digest(self.workspace_source_sha256)
        _digest(self.binding_sha256)
        if type(self.training) is not tuple or type(self.held_out) is not tuple:
            _fail(
                "INVALID_SPLIT",
                "Immutable explicit training and held-out tuples are required",
            )
        if not 3 <= len(self.training) or not 1 <= len(self.held_out):
            _fail(
                "INSUFFICIENT_POINTS",
                "At least three training and one untouched held-out point are required",
            )
        if len(self.training) + len(self.held_out) > MAX_POINTS:
            _fail(
                "TOO_MANY_POINTS", "Correspondence count exceeds the fixed work limit"
            )
        seen: set[str] = set()
        for pair in self.training + self.held_out:
            if type(pair) is not RigidPointPair:
                _fail(
                    "INVALID_POINT",
                    "Every correspondence must be an exact RigidPointPair",
                )
            pair.__post_init__()
            if pair.pair_id in seen:
                _fail(
                    "DUPLICATE_ID_OR_SPLIT_LEAKAGE",
                    "IDs cannot repeat within or across partitions",
                )
            seen.add(pair.pair_id)
            if (
                pair.source.frame != self.source_frame
                or pair.target.frame != self.target_frame
            ):
                _fail(
                    "FRAME_OR_UNIT_MISMATCH",
                    "Point frames differ from the declared transform direction",
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "rocell.rigid_correspondence_input.v1",
            "dataset_id": self.dataset_id,
            "source_frame": self.source_frame,
            "target_frame": self.target_frame,
            "units": self.units,
            "training": [pair.to_dict() for pair in self.training],
            "held_out": [pair.to_dict() for pair in self.held_out],
            "workspace_source_sha256": self.workspace_source_sha256,
            "binding_sha256": self.binding_sha256,
            "origin": self.origin.value,
        }

    @property
    def input_sha256(self) -> str:
        return _hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class RigidCorrespondencePolicy:
    policy_id: str = "RIGID-CORRESPONDENCE-DIAGNOSTIC-001"
    minimum_training_points: int = 3
    minimum_held_out_points: int = 1
    maximum_points: int = MAX_POINTS
    minimum_point_separation_mm: float = 0.000001
    rank_relative_tolerance: float = 0.000000001
    minimum_second_axis_rms_mm: float = 0.1
    maximum_inplane_condition: float = 10000.0
    maximum_training_rms_mm: float = 0.5
    maximum_training_residual_mm: float = 1.0
    maximum_held_out_rms_mm: float = 0.75
    maximum_held_out_residual_mm: float = 1.5
    maximum_training_pair_distance_error_mm: float = 1.0

    def __post_init__(self) -> None:
        _identifier(self.policy_id)
        for name, minimum in (
            ("minimum_training_points", 3),
            ("minimum_held_out_points", 1),
            ("maximum_points", 4),
        ):
            value = getattr(self, name)
            if type(value) is not int or not minimum <= value <= MAX_POINTS:
                _fail("INVALID_POLICY", "Point-count policy exceeds fixed limits")
        if (
            self.minimum_training_points + self.minimum_held_out_points
            > self.maximum_points
        ):
            _fail("INVALID_POLICY", "Partition minima exceed maximum points")
        for name in (
            "minimum_point_separation_mm",
            "rank_relative_tolerance",
            "minimum_second_axis_rms_mm",
            "maximum_inplane_condition",
            "maximum_training_rms_mm",
            "maximum_training_residual_mm",
            "maximum_held_out_rms_mm",
            "maximum_held_out_residual_mm",
            "maximum_training_pair_distance_error_mm",
        ):
            value = _number(getattr(self, name), MAX_COORDINATE_MM)
            if value <= 0.0:
                _fail("INVALID_POLICY", "Numerical policy limits must be positive")
            object.__setattr__(self, name, value)
        if not 1e-10 <= self.rank_relative_tolerance <= 0.001:
            _fail(
                "INVALID_POLICY",
                "Rank threshold is outside the supported numerical interval",
            )
        if not 1.0 <= self.maximum_inplane_condition <= 10000.0:
            _fail(
                "INVALID_POLICY",
                "In-plane condition policy cannot relax the numerical ceiling",
            )
        if (
            self.minimum_point_separation_mm < 1e-9
            or self.minimum_second_axis_rms_mm < 1e-6
        ):
            _fail(
                "INVALID_POLICY",
                "Geometric excitation cannot be below numerical resolution",
            )
        if (
            self.maximum_training_rms_mm > self.maximum_training_residual_mm
            or self.maximum_held_out_rms_mm > self.maximum_held_out_residual_mm
        ):
            _fail("INVALID_POLICY", "RMS limits cannot exceed maximum-residual limits")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def policy_sha256(self) -> str:
        return _hash(self.to_dict())


DEFAULT_RIGID_CORRESPONDENCE_POLICY = RigidCorrespondencePolicy()


def _xyz(point: Point3Mm) -> tuple[float, float, float]:
    return point.x, point.y, point.z


def _distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return math.sqrt(math.fsum((a - b) ** 2 for a, b in zip(left, right)))


def _validate_inputs(
    data: RigidCorrespondenceInput, policy: RigidCorrespondencePolicy
) -> None:
    if (
        type(data) is not RigidCorrespondenceInput
        or type(policy) is not RigidCorrespondencePolicy
    ):
        _fail(
            "INVALID_INPUT_TYPE", "Exact immutable input and policy types are required"
        )
    data.__post_init__()
    policy.__post_init__()
    if (
        len(data.training) < policy.minimum_training_points
        or len(data.held_out) < policy.minimum_held_out_points
        or len(data.training) + len(data.held_out) > policy.maximum_points
    ):
        _fail(
            "INSUFFICIENT_POINTS",
            "Dataset differs from the explicit partition/count policy",
        )
    all_points = data.training + data.held_out
    # Geometry is checked across partitions too: changing an ID does not make a
    # reused measurement an untouched held-out observation.
    for index, pair in enumerate(all_points):
        for previous in all_points[:index]:
            if (
                _distance(_xyz(pair.source), _xyz(previous.source))
                <= policy.minimum_point_separation_mm
                or _distance(_xyz(pair.target), _xyz(previous.target))
                <= policy.minimum_point_separation_mm
            ):
                _fail(
                    "DUPLICATE_GEOMETRY_OR_SPLIT_LEAKAGE",
                    "Repeated/near-repeated source or target geometry is not independent data",
                )


def _transpose(a: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(a[column * 3 + row] for row in range(3) for column in range(3))


def _multiply(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(
        math.fsum(a[row * 3 + k] * b[k * 3 + column] for k in range(3))
        for row in range(3)
        for column in range(3)
    )


def _det(a: tuple[float, ...]) -> float:
    return (
        a[0] * (a[4] * a[8] - a[5] * a[7])
        - a[1] * (a[3] * a[8] - a[5] * a[6])
        + a[2] * (a[3] * a[7] - a[4] * a[6])
    )


def _diagonal(values: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(
        values[row] if row == column else 0.0 for row in range(3) for column in range(3)
    )


def _close_matrices(actual: tuple[float, ...], expected: tuple[float, ...]) -> bool:
    # Fixed numerical certificate tolerance, not an adjustable acceptance gate.
    tolerance = max(1e-12, max(abs(x) for x in expected) * 2e-10)
    return max(abs(a - b) for a, b in zip(actual, expected)) <= tolerance


def _centered(data: RigidCorrespondenceInput):
    source, target = tuple(_xyz(p.source) for p in data.training), tuple(
        _xyz(p.target) for p in data.training
    )
    count = len(source)
    source_mean = tuple(math.fsum(p[k] for p in source) / count for k in range(3))
    target_mean = tuple(math.fsum(p[k] for p in target) / count for k in range(3))
    x = tuple(tuple(p[k] - source_mean[k] for k in range(3)) for p in source)
    y = tuple(tuple(p[k] - target_mean[k] for k in range(3)) for p in target)
    return source_mean, target_mean, x, y


def _cross(a, b) -> tuple[float, ...]:
    return tuple(
        math.fsum(left[row] * right[column] for left, right in zip(a, b))
        for row in range(3)
        for column in range(3)
    )


def _certificate_values(
    certificate: dict[str, Any], name: str, size: int
) -> tuple[float, ...]:
    value = certificate[name]
    if type(value) is not list or len(value) != size:
        _fail("INVALID_CERTIFICATE", "Spectral certificate dimensions differ")
    return tuple(_number(item) for item in value)


def _certified_transform(data, policy, certificate):
    """Verify supplied SVD factors algebraically; this is not a new SVD/fit."""
    if type(certificate) is not dict or set(certificate) != _CERTIFICATE_FIELDS:
        _fail(
            "INVALID_CERTIFICATE",
            "Exact versioned spectral certificate fields required",
        )
    sx, sy, sh = (
        _certificate_values(certificate, key, 3)
        for key in (
            "source_singular_values_mm",
            "target_singular_values_mm",
            "cross_singular_values_mm2",
        )
    )
    vx, vy, uh, vh = (
        _certificate_values(certificate, key, 9)
        for key in (
            "source_right_basis",
            "target_right_basis",
            "cross_left_basis",
            "cross_right_basis",
        )
    )
    for values in (sx, sy, sh):
        if (
            any(value < 0 for value in values)
            or tuple(sorted(values, reverse=True)) != values
        ):
            _fail(
                "INVALID_CERTIFICATE",
                "Singular values must be nonnegative and descending",
            )
    for basis in (vx, vy, uh, vh):
        if not _close_matrices(_multiply(_transpose(basis), basis), _IDENTITY):
            _fail("INVALID_CERTIFICATE", "Singular vector bases are not orthonormal")
    source_mean, target_mean, x, y = _centered(data)
    for values, basis, gram in ((sx, vx, _cross(x, x)), (sy, vy, _cross(y, y))):
        reconstructed = _multiply(
            _multiply(basis, _diagonal(tuple(s * s for s in values))), _transpose(basis)
        )
        if not _close_matrices(reconstructed, gram):
            _fail(
                "INVALID_CERTIFICATE",
                "Training excitation certificate differs from actual points",
            )
    cross = _cross(x, y)
    if not _close_matrices(
        _multiply(_multiply(uh, _diagonal(sh)), _transpose(vh)), cross
    ):
        _fail(
            "INVALID_CERTIFICATE",
            "Cross-covariance certificate differs from actual training pairs",
        )
    ranks = tuple(
        sum(
            value > max(1e-12, values[0] * policy.rank_relative_tolerance)
            for value in values
        )
        for values in (sx, sy, sh)
    )
    if min(ranks) < 2:
        _fail(
            "DEGENERATE_TRAINING",
            "Training correspondences must excite two independent axes",
        )
    conditions = sx[0] / sx[1], sy[0] / sy[1]
    spreads = sx[1] / math.sqrt(len(x)), sy[1] / math.sqrt(len(x))
    if (
        min(spreads) < policy.minimum_second_axis_rms_mm
        or max(conditions) > policy.maximum_inplane_condition
    ):
        _fail(
            "DEGENERATE_TRAINING", "Training excitation is too small or ill-conditioned"
        )
    # H = U S V^T. R = V diag(1,1,det(VU^T)) U^T is the global
    # least-squares proper-rotation optimum; it cannot fit scale or reflection.
    parity = -1.0 if _det(_multiply(vh, _transpose(uh))) < 0.0 else 1.0
    rotation = Rotation3(
        _multiply(_multiply(vh, _diagonal((1.0, 1.0, parity))), _transpose(uh))
    )
    translation = Vec3(*target_mean) - rotation.apply(Vec3(*source_mean))
    transform = RigidTransform(
        data.target_frame, data.source_frame, rotation, translation
    )
    observability = {
        "source_rank": ranks[0],
        "target_rank": ranks[1],
        "cross_rank": ranks[2],
        "source_inplane_condition": conditions[0],
        "target_inplane_condition": conditions[1],
        "source_second_axis_rms_mm": spreads[0],
        "target_second_axis_rms_mm": spreads[1],
        "proper_rotation_determinant": _det(rotation.matrix),
        "full_rank_reflection_detected": min(ranks) == 3 and parity < 0.0,
        "planar_handedness_not_independently_observable": min(ranks) < 3,
    }
    return transform, observability


def _transform_document(transform: RigidTransform) -> dict[str, Any]:
    return {
        "target_frame": transform.parent_frame,
        "source_frame": transform.child_frame,
        "rotation_row_major": list(transform.rotation.matrix),
        "translation_mm": list(
            _xyz(
                Point3Mm(
                    transform.parent_frame,
                    transform.translation_mm.x,
                    transform.translation_mm.y,
                    transform.translation_mm.z,
                )
            )
        ),
    }


def _report(data, policy, certificate, numpy_version):
    transform, observability = _certified_transform(data, policy, certificate)
    rows: list[dict[str, Any]] = []
    summaries = {}
    for split, pairs in (("TRAINING", data.training), ("HELD_OUT", data.held_out)):
        errors = []
        for pair in pairs:
            predicted = transform.transform_point(pair.source)
            delta = tuple(a - b for a, b in zip(_xyz(predicted), _xyz(pair.target)))
            error = math.sqrt(math.fsum(value * value for value in delta))
            errors.append(error)
            rows.append(
                {
                    "pair_id": pair.pair_id,
                    "split": split,
                    "predicted_target_mm": list(_xyz(predicted)),
                    "error_target_mm": list(delta),
                    "residual_mm": error,
                }
            )
        summaries[split] = {
            "count": len(errors),
            "rms_mm": math.sqrt(
                math.fsum(value * value for value in errors) / len(errors)
            ),
            "maximum_mm": max(errors),
        }
    pair_error = max(
        abs(
            _distance(_xyz(a.source), _xyz(b.source))
            - _distance(_xyz(a.target), _xyz(b.target))
        )
        for i, a in enumerate(data.training)
        for b in data.training[:i]
    )
    failures = []
    for reason, actual, limit in (
        (
            "TRAINING_RMS_EXCEEDED",
            summaries["TRAINING"]["rms_mm"],
            policy.maximum_training_rms_mm,
        ),
        (
            "TRAINING_MAXIMUM_EXCEEDED",
            summaries["TRAINING"]["maximum_mm"],
            policy.maximum_training_residual_mm,
        ),
        (
            "HELD_OUT_RMS_EXCEEDED",
            summaries["HELD_OUT"]["rms_mm"],
            policy.maximum_held_out_rms_mm,
        ),
        (
            "HELD_OUT_MAXIMUM_EXCEEDED",
            summaries["HELD_OUT"]["maximum_mm"],
            policy.maximum_held_out_residual_mm,
        ),
        (
            "NONRIGID_TRAINING_DISTANCES",
            pair_error,
            policy.maximum_training_pair_distance_error_mm,
        ),
    ):
        if actual > limit:
            failures.append(reason)
    if observability["full_rank_reflection_detected"]:
        failures.append("REFLECTED_FULL_RANK_CORRESPONDENCES")
    return {
        "schema": SCHEMA,
        "solver": "NUMPY_KABSCH_PROPER_RIGID_V1",
        "numpy_version": numpy_version,
        "input": data.to_dict(),
        "input_sha256": data.input_sha256,
        "policy": policy.to_dict(),
        "policy_sha256": policy.policy_sha256,
        "candidate_transform": _transform_document(transform),
        "spectral_certificate": certificate,
        "observability": observability,
        "training_summary": summaries["TRAINING"],
        "held_out_summary": summaries["HELD_OUT"],
        "maximum_training_pair_distance_error_mm": pair_error,
        "residuals": rows,
        "diagnostic_pass": not failures,
        "diagnostic_failures": failures,
        "status": (
            "DIAGNOSTIC_PASS_CANDIDATE_ONLY"
            if not failures
            else "DIAGNOSTIC_FAIL_CANDIDATE_ONLY"
        ),
        "provenance": {
            "origin": data.origin.value,
            "workspace_source_sha256": data.workspace_source_sha256,
            "binding_sha256": data.binding_sha256,
            "fit_partition": "TRAINING_ONLY",
            "held_out_used_for_fit": False,
            "units": "DECLARED_MM_NOT_PHYSICALLY_VERIFIED",
            "scale_or_shear_fitted": False,
            "physical_calibration_qualified": False,
            "physical_authority": False,
            "hardware_accessed": False,
            "registry_written": False,
            "physical_release_effect": "NONE",
        },
        "limitations": [
            "Candidate geometry only; no firmware, joint reference, controller correlation, TCP or power state is established.",
            "A planar correspondence set cannot independently distinguish an ambient-space reflection from an equivalent proper rotation on its plane.",
            "Caller-supplied origin, units and source hashes are binding labels, not verified measurement provenance or approved physical thresholds.",
        ],
    }


@dataclass(frozen=True, slots=True)
class RigidCorrespondenceResult:
    _payload: bytes

    def canonical_bytes(self) -> bytes:
        return self._payload

    @property
    def report_sha256(self) -> str:
        return hashlib.sha256(self._payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._payload)

    @property
    def diagnostic_pass(self) -> bool:
        return bool(self.to_dict()["diagnostic_pass"])

    @property
    def diagnostic_failures(self) -> tuple[str, ...]:
        return tuple(self.to_dict()["diagnostic_failures"])

    @property
    def candidate_transform(self) -> RigidTransform:
        value = self.to_dict()["candidate_transform"]
        return RigidTransform(
            value["target_frame"],
            value["source_frame"],
            Rotation3(tuple(value["rotation_row_major"])),
            Vec3(*value["translation_mm"]),
        )


def fit_rigid_correspondence(
    data: RigidCorrespondenceInput,
    *,
    policy: RigidCorrespondencePolicy = DEFAULT_RIGID_CORRESPONDENCE_POLICY,
) -> RigidCorrespondenceResult:
    """Fit target_T_source from training only; evaluate untouched held-out pairs."""
    _validate_inputs(data, policy)
    try:
        np = importlib.import_module("numpy")
    except Exception as exc:
        raise RigidCorrespondenceUnavailable(
            "Rigid correspondence fitting requires optional NumPy; no fit was performed"
        ) from exc
    _, _, x, y = _centered(data)
    try:
        _, sx, vxt = np.linalg.svd(np.asarray(x, dtype=float), full_matrices=False)
        _, sy, vyt = np.linalg.svd(np.asarray(y, dtype=float), full_matrices=False)
        uh, sh, vht = np.linalg.svd(np.asarray(_cross(x, y), dtype=float).reshape(3, 3))
    except Exception as exc:
        raise RigidCorrespondenceError(
            "NUMERICAL_FAILURE", "SVD did not produce a candidate"
        ) from exc
    certificate = {
        "source_singular_values_mm": [float(v) for v in sx],
        "target_singular_values_mm": [float(v) for v in sy],
        "cross_singular_values_mm2": [float(v) for v in sh],
        "source_right_basis": [float(v) for v in vxt.T.flat],
        "target_right_basis": [float(v) for v in vyt.T.flat],
        "cross_left_basis": [float(v) for v in uh.flat],
        "cross_right_basis": [float(v) for v in vht.T.flat],
    }
    payload = _canonical(_report(data, policy, certificate, str(np.__version__)))
    return verify_rigid_correspondence_result(
        payload,
        expected_input=data,
        expected_policy=policy,
        expected_evidence_sha256=hashlib.sha256(payload).hexdigest(),
    )


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("DUPLICATE_JSON_KEY", "Duplicate retained JSON field")
        result[key] = value
    return result


def _tree(value: object, depth: int = 0) -> None:
    if depth > 12:
        _fail("INVALID_EVIDENCE", "Retained JSON nesting exceeds its limit")
    if type(value) is dict:
        if len(value) > 32:
            _fail("INVALID_EVIDENCE", "Too many retained object fields")
        for key, child in value.items():
            if type(key) is not str or len(key) > 128:
                _fail("INVALID_EVIDENCE", "Retained key is not bounded")
            _tree(child, depth + 1)
    elif type(value) is list:
        if len(value) > MAX_POINTS:
            _fail("INVALID_EVIDENCE", "Retained array exceeds point limit")
        for child in value:
            _tree(child, depth + 1)
    elif type(value) is str:
        if len(value) > 512:
            _fail("INVALID_EVIDENCE", "Retained string exceeds its limit")
    elif type(value) in (int, float):
        _number(value)
    elif value is not None and type(value) is not bool:
        _fail("INVALID_EVIDENCE", "Unsupported retained JSON value")


def verify_rigid_correspondence_result(
    payload: bytes,
    *,
    expected_input: RigidCorrespondenceInput,
    expected_policy: RigidCorrespondencePolicy,
    expected_evidence_sha256: str,
) -> RigidCorrespondenceResult:
    """Pure bounded algebraic verification from independently trusted references.

    No NumPy import, file read, solver replay or physical qualification occurs.
    SVD factors are checked against training covariance, and the proper Kabsch
    optimum/residuals are reconstructed with fixed-size scalar arithmetic.
    """
    _validate_inputs(expected_input, expected_policy)
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_EVIDENCE_BYTES:
        _fail(
            "INVALID_EVIDENCE", "A bounded complete canonical byte payload is required"
        )
    if hashlib.sha256(payload).hexdigest() != _digest(expected_evidence_sha256):
        _fail(
            "EVIDENCE_HASH_MISMATCH", "Retained evidence differs from the trusted hash"
        )
    try:
        document = json.loads(
            payload,
            object_pairs_hook=_pairs,
            parse_constant=lambda _: _fail("INVALID_NUMBER", "Nonfinite JSON constant"),
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise RigidCorrespondenceError(
            "INVALID_EVIDENCE", "Retained evidence is not bounded JSON"
        ) from exc
    _tree(document)
    if type(document) is not dict:
        _fail("INVALID_EVIDENCE", "Retained result must be an object")
    version = document.get("numpy_version")
    if type(version) is not str or not re.fullmatch(r"[A-Za-z0-9_.+-]{1,64}", version):
        _fail("INVALID_EVIDENCE", "An exact bounded recorded NumPy version is required")
    expected = _report(
        expected_input, expected_policy, document.get("spectral_certificate"), version
    )
    # Canonical byte equality rejects unknown keys, bool/int substitutions,
    # changed partitions, thresholds, result flags, units and numeric residuals.
    if _canonical(expected) != payload or _canonical(document) != payload:
        _fail(
            "EVIDENCE_SEMANTICS_MISMATCH",
            "Retained report differs from independently reconstructed inputs and algebra",
        )
    return RigidCorrespondenceResult(payload)


__all__ = [
    "SCHEMA",
    "MAX_POINTS",
    "MAX_EVIDENCE_BYTES",
    "CorrespondenceOrigin",
    "RigidCorrespondenceError",
    "RigidCorrespondenceUnavailable",
    "RigidPointPair",
    "RigidCorrespondenceInput",
    "RigidCorrespondencePolicy",
    "RigidCorrespondenceResult",
    "DEFAULT_RIGID_CORRESPONDENCE_POLICY",
    "fit_rigid_correspondence",
    "verify_rigid_correspondence_result",
]
