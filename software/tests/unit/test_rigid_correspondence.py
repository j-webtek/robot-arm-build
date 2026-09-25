"""Offline analytic-oracle tests; no devices, registry or transport are used."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import math

import pytest

from rocell.calibration import rigid_correspondence as fit
from rocell.geometry.transforms import RigidTransform, Rotation3, Vec3
from rocell.models.frames import Point3Mm


TRUTH = RigidTransform.from_rpy_translation_mm(
    "board",
    "arm_base",
    translation_mm=Vec3(120, -35, 18),
    roll_rad=0.2,
    pitch_rad=-0.3,
    yaw_rad=0.4,
)
TRAINING = ((0, 0, 0), (40, 0, 0), (0, 30, 0), (0, 0, 20), (-20, 10, 15), (15, -18, 8))
HELD_OUT = ((12, 18, -8), (-4, -12, 27))


def dataset(training=TRAINING, held_out=HELD_OUT, target=None):
    def pair(index, coordinates):
        source = Point3Mm("arm_base", *coordinates)
        observed = (
            TRUTH.transform_point(source)
            if target is None
            else Point3Mm("board", *target(coordinates))
        )
        return fit.RigidPointPair(f"p{index}", source, observed)

    return fit.RigidCorrespondenceInput(
        "rigid-fixture",
        "arm_base",
        "board",
        tuple(pair(i, xyz) for i, xyz in enumerate(training)),
        tuple(pair(i + len(training), xyz) for i, xyz in enumerate(held_out)),
        "a" * 64,
        "b" * 64,
        fit.CorrespondenceOrigin.SYNTHETIC_REHEARSAL_ONLY,
    )


def verify(
    result, data, *, payload=None, policy=fit.DEFAULT_RIGID_CORRESPONDENCE_POLICY
):
    value = result.canonical_bytes() if payload is None else payload
    return fit.verify_rigid_correspondence_result(
        value,
        expected_input=data,
        expected_policy=policy,
        expected_evidence_sha256=hashlib.sha256(value).hexdigest(),
    )


def encoded(document):
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


@pytest.fixture(scope="module")
def nominal():
    data = dataset()
    return data, fit.fit_rigid_correspondence(data)


def test_analytic_truth_recovers_proper_target_t_source_and_all_residuals(nominal):
    data, result = nominal
    assert result.diagnostic_pass
    assert result.diagnostic_failures == ()
    assert result.candidate_transform.almost_equal(TRUTH, absolute_tolerance=1e-10)
    document = result.to_dict()
    assert document["input_sha256"] == data.input_sha256
    assert (
        document["policy_sha256"]
        == fit.DEFAULT_RIGID_CORRESPONDENCE_POLICY.policy_sha256
    )
    assert len(document["residuals"]) == 8
    assert document["training_summary"]["count"] == 6
    assert document["held_out_summary"]["count"] == 2
    assert document["observability"]["source_rank"] == 3
    assert document["observability"]["proper_rotation_determinant"] == pytest.approx(
        1.0
    )
    for row, pair in zip(document["residuals"], data.training + data.held_out):
        predicted = TRUTH.transform_point(pair.source)
        assert row["predicted_target_mm"] == pytest.approx(
            (predicted.x, predicted.y, predicted.z), abs=1e-10
        )
        assert row["residual_mm"] < 1e-10
    assert verify(result, data).canonical_bytes() == result.canonical_bytes()


def test_planar_noncollinear_training_is_supported():
    data = dataset(
        training=((0, 0, 0), (40, 0, 0), (0, 30, 0), (30, 20, 0)),
        held_out=((15, 7, 0), (-6, 18, 0)),
    )
    result = fit.fit_rigid_correspondence(data)
    assert result.diagnostic_pass
    assert result.candidate_transform.almost_equal(TRUTH, absolute_tolerance=1e-9)
    assert result.to_dict()["observability"]["source_rank"] == 2
    assert (
        result.to_dict()["observability"][
            "planar_handedness_not_independently_observable"
        ]
        is True
    )


def test_minimal_three_noncollinear_training_and_one_heldout():
    data = dataset(training=TRAINING[:3], held_out=HELD_OUT[:1])
    result = fit.fit_rigid_correspondence(data)
    assert result.diagnostic_pass
    assert result.candidate_transform.almost_equal(TRUTH, absolute_tolerance=1e-9)


def test_deterministic_small_noise_gives_candidate_with_measured_residuals():
    data = dataset()

    def noisy(index, pair):
        return replace(
            pair,
            target=Point3Mm(
                "board",
                pair.target.x + (index % 3 - 1) * 0.03,
                pair.target.y + (-1) ** index * 0.02,
                pair.target.z + (index % 2) * 0.04,
            ),
        )

    data = replace(
        data,
        training=tuple(noisy(i, p) for i, p in enumerate(data.training)),
        held_out=tuple(noisy(i + 6, p) for i, p in enumerate(data.held_out)),
    )
    result = fit.fit_rigid_correspondence(data)
    assert result.diagnostic_pass
    assert 0.005 < result.to_dict()["training_summary"]["rms_mm"] < 0.1
    assert 0.0 < result.to_dict()["held_out_summary"]["rms_mm"] < 0.1
    assert result.candidate_transform.translation_mm.almost_equal(
        TRUTH.translation_mm, absolute_tolerance=0.1
    )


def test_heldout_fault_does_not_move_the_fit_or_enter_training_certificate(nominal):
    data, nominal_result = nominal
    altered = replace(
        data,
        held_out=tuple(
            replace(p, target=Point3Mm("board", p.target.x + 7, p.target.y, p.target.z))
            for p in data.held_out
        ),
    )
    result = fit.fit_rigid_correspondence(altered)
    assert result.candidate_transform == nominal_result.candidate_transform
    assert (
        result.to_dict()["spectral_certificate"]
        == nominal_result.to_dict()["spectral_certificate"]
    )
    assert (
        result.to_dict()["training_summary"]
        == nominal_result.to_dict()["training_summary"]
    )
    assert not result.diagnostic_pass
    assert result.diagnostic_failures == (
        "HELD_OUT_RMS_EXCEEDED",
        "HELD_OUT_MAXIMUM_EXCEEDED",
    )
    assert result.to_dict()["held_out_summary"]["rms_mm"] == pytest.approx(7.0)
    assert verify(result, altered).diagnostic_pass is False


@pytest.mark.parametrize("scale", [0.001, 0.8, 1.2, 1000.0])
def test_scale_or_units_disagreement_is_not_fitted_away(scale):
    data = dataset(target=lambda p: tuple(scale * v for v in p))
    # The very small target may be rejected for excitation before residuals.
    try:
        result = fit.fit_rigid_correspondence(data)
    except fit.RigidCorrespondenceError as exc:
        assert exc.code == "DEGENERATE_TRAINING"
    else:
        assert not result.diagnostic_pass
        assert "NONRIGID_TRAINING_DISTANCES" in result.diagnostic_failures
        assert result.to_dict()["provenance"]["scale_or_shear_fitted"] is False


def test_full_rank_reflection_cannot_be_accepted_even_with_loose_residual_policy():
    data = dataset(target=lambda p: (-p[0], p[1], p[2]))
    policy = replace(
        fit.DEFAULT_RIGID_CORRESPONDENCE_POLICY,
        maximum_training_rms_mm=1000,
        maximum_training_residual_mm=1000,
        maximum_held_out_rms_mm=1000,
        maximum_held_out_residual_mm=1000,
    )
    result = fit.fit_rigid_correspondence(data, policy=policy)
    assert not result.diagnostic_pass
    assert result.diagnostic_failures == ("REFLECTED_FULL_RANK_CORRESPONDENCES",)
    assert result.to_dict()["observability"][
        "proper_rotation_determinant"
    ] == pytest.approx(1)


def test_planar_mirror_limit_is_explicit_not_a_false_detection_claim():
    data = dataset(
        training=((0, 0, 0), (40, 0, 0), (0, 30, 0)),
        held_out=((17, 11, 0),),
        target=lambda p: (-p[0], p[1], p[2]),
    )
    result = fit.fit_rigid_correspondence(data)
    assert result.diagnostic_pass
    observability = result.to_dict()["observability"]
    assert observability["full_rank_reflection_detected"] is False
    assert observability["planar_handedness_not_independently_observable"] is True
    assert result.to_dict()["provenance"]["physical_calibration_qualified"] is False


def test_shear_and_mismatched_pair_order_fail_residual_policy():
    shear = dataset(target=lambda p: (p[0] + 0.3 * p[1], p[1], p[2]))
    assert not fit.fit_rigid_correspondence(shear).diagnostic_pass
    original = dataset()
    altered = replace(
        original,
        training=tuple(
            replace(p, target=original.training[(i + 1) % 6].target)
            for i, p in enumerate(original.training)
        ),
    )
    assert not fit.fit_rigid_correspondence(altered).diagnostic_pass


@pytest.mark.parametrize(
    "training",
    [
        ((0, 0, 0), (1, 0, 0), (2, 0, 0)),
        ((0, 0, 0), (1, 0, 0), (2, 0.00001, 0)),
        ((0, 0, 0), (0.00001, 0, 0), (0, 0.00001, 0)),
    ],
)
def test_collinear_small_or_ill_conditioned_training_fails_closed(training):
    with pytest.raises(fit.RigidCorrespondenceError) as error:
        fit.fit_rigid_correspondence(dataset(training=training))
    assert error.value.code == "DEGENERATE_TRAINING"


def test_collapsed_target_and_reused_geometry_are_not_independent_observations(nominal):
    data, _ = nominal
    for changed in (
        replace(
            data,
            held_out=(replace(data.training[0], pair_id="held-copy"), data.held_out[1]),
        ),
        replace(
            data,
            training=(
                data.training[0],
                replace(data.training[1], target=data.training[0].target),
                *data.training[2:],
            ),
        ),
    ):
        with pytest.raises(fit.RigidCorrespondenceError) as error:
            fit.fit_rigid_correspondence(changed)
        assert error.value.code == "DUPLICATE_GEOMETRY_OR_SPLIT_LEAKAGE"


def test_duplicate_ids_across_partitions_are_rejected():
    data = dataset()
    with pytest.raises(fit.RigidCorrespondenceError) as error:
        replace(
            data,
            held_out=(replace(data.held_out[0], pair_id=data.training[0].pair_id),),
        )
    assert error.value.code == "DUPLICATE_ID_OR_SPLIT_LEAKAGE"


@pytest.mark.parametrize(
    "change",
    [
        {"units": "m"},
        {"source_frame": "board"},
        {"target_frame": "arm_base"},
        {"source_frame": "R_ctrl"},
        {"training": []},
        {"origin": "SYNTHETIC_REHEARSAL_ONLY"},
        {"workspace_source_sha256": "0" * 64},
        {"binding_sha256": "A" * 64},
        {"dataset_id": "../outside"},
    ],
)
def test_exact_frames_units_types_and_provenance_are_required(change):
    with pytest.raises(fit.RigidCorrespondenceError):
        replace(dataset(), **change)


def test_reversing_both_declared_frames_and_pairs_is_an_explicit_inverse_not_alias():
    data = dataset()
    reversed_data = replace(
        data,
        source_frame="board",
        target_frame="arm_base",
        training=tuple(
            replace(p, source=p.target, target=p.source) for p in data.training
        ),
        held_out=tuple(
            replace(p, source=p.target, target=p.source) for p in data.held_out
        ),
    )
    result = fit.fit_rigid_correspondence(reversed_data)
    assert result.candidate_transform.almost_equal(
        TRUTH.inverse(), absolute_tolerance=1e-9
    )
    assert reversed_data.input_sha256 != data.input_sha256


@pytest.mark.parametrize("value", [math.nan, math.inf, True, "1", 1_000_001])
def test_coordinate_boundary_rejects_invalid_or_oversize_values(value):
    with pytest.raises((ValueError, TypeError)):
        fit.RigidPointPair(
            "p", Point3Mm("source", value, 0, 0), Point3Mm("target", 0, 0, 0)
        )


@pytest.mark.parametrize(
    "change",
    [
        {"minimum_training_points": 2},
        {"minimum_held_out_points": 0},
        {"maximum_points": 129},
        {"minimum_training_points": True},
        {"rank_relative_tolerance": 0},
        {"maximum_inplane_condition": 10001},
        {"maximum_training_rms_mm": 2},
        {"minimum_point_separation_mm": -1},
        {"minimum_second_axis_rms_mm": 1e-12},
    ],
)
def test_policy_cannot_remove_numerical_or_resource_floors(change):
    with pytest.raises(fit.RigidCorrespondenceError):
        replace(fit.DEFAULT_RIGID_CORRESPONDENCE_POLICY, **change)


def test_point_count_limit_and_partition_minima():
    data = dataset()
    with pytest.raises(fit.RigidCorrespondenceError):
        replace(data, training=data.training[:2])
    with pytest.raises(fit.RigidCorrespondenceError):
        replace(data, held_out=())
    pairs = tuple(replace(data.training[0], pair_id=f"p{i}") for i in range(129))
    with pytest.raises(fit.RigidCorrespondenceError):
        replace(data, training=pairs)


def test_result_and_input_views_are_immutable_and_copy_isolated(nominal):
    data, result = nominal
    before = result.canonical_bytes()
    document = result.to_dict()
    document["input"]["training"][0]["source"]["xyz_mm"][0] = 99
    document["candidate_transform"]["translation_mm"][0] = 999
    document["diagnostic_failures"].append("fabricated")
    data.to_dict()["held_out"].clear()
    fit.DEFAULT_RIGID_CORRESPONDENCE_POLICY.to_dict()["maximum_points"] = 0
    assert result.canonical_bytes() == before
    assert result.diagnostic_pass and len(data.held_out) == 2
    with pytest.raises(FrozenInstanceError):
        data.dataset_id = "changed"
    with pytest.raises(FrozenInstanceError):
        result._payload = b"{}"


@pytest.mark.parametrize(
    "field",
    [
        "candidate_transform",
        "input",
        "policy",
        "residuals",
        "observability",
        "diagnostic_pass",
        "provenance",
    ],
)
def test_rehashed_semantic_tampering_is_rejected(nominal, field):
    data, result = nominal
    document = result.to_dict()
    if field == "candidate_transform":
        document[field]["translation_mm"][0] += 1
    elif field == "input":
        document[field]["held_out"][0]["target"]["xyz_mm"][0] += 1
    elif field == "policy":
        document[field]["maximum_held_out_rms_mm"] = 100
    elif field == "residuals":
        document[field][0]["residual_mm"] = 1
    elif field == "observability":
        document[field]["source_rank"] = 2
    elif field == "diagnostic_pass":
        document[field] = 1
    else:
        document[field]["physical_calibration_qualified"] = True
    with pytest.raises(fit.RigidCorrespondenceError):
        verify(result, data, payload=encoded(document))


@pytest.mark.parametrize("field", sorted(fit._CERTIFICATE_FIELDS))
def test_rehashed_spectral_certificate_tampering_is_rejected(nominal, field):
    data, result = nominal
    document = result.to_dict()
    document["spectral_certificate"][field][0] += 3
    with pytest.raises(fit.RigidCorrespondenceError):
        verify(result, data, payload=encoded(document))


def test_strict_parser_rejects_unknown_duplicate_noncanonical_and_oversize(nominal):
    data, result = nominal
    document = result.to_dict()
    document["unknown"] = 1
    payloads = [
        encoded(document),
        result.canonical_bytes().replace(
            b'{"candidate_transform":',
            b'{"schema":"duplicate","candidate_transform":',
            1,
        ),
        b"[]",
        b"{}" + b" " * fit.MAX_EVIDENCE_BYTES,
        json.dumps(result.to_dict()).encode(),
        b'{"value":NaN}',
    ]
    for payload in payloads:
        with pytest.raises(fit.RigidCorrespondenceError):
            verify(result, data, payload=payload)


def test_verifier_requires_independently_supplied_input_policy_and_hash(nominal):
    data, result = nominal
    with pytest.raises(fit.RigidCorrespondenceError):
        fit.verify_rigid_correspondence_result(
            result.canonical_bytes(),
            expected_input=data,
            expected_policy=fit.DEFAULT_RIGID_CORRESPONDENCE_POLICY,
            expected_evidence_sha256="f" * 64,
        )
    with pytest.raises(fit.RigidCorrespondenceError):
        verify(result, replace(data, binding_sha256="c" * 64))
    with pytest.raises(fit.RigidCorrespondenceError):
        verify(
            result,
            data,
            policy=replace(
                fit.DEFAULT_RIGID_CORRESPONDENCE_POLICY, maximum_held_out_rms_mm=0.8
            ),
        )


def test_verifier_never_imports_numpy_or_calls_fit(nominal, monkeypatch):
    data, result = nominal

    def forbidden(*args, **kwargs):
        raise AssertionError("pure verification must not replay numerical fit/import")

    monkeypatch.setattr(fit.importlib, "import_module", forbidden)
    monkeypatch.setattr(fit, "fit_rigid_correspondence", forbidden)
    assert verify(result, data).canonical_bytes() == result.canonical_bytes()


def test_numpy_unavailable_has_no_fallback_or_candidate(monkeypatch):
    def missing(*args, **kwargs):
        raise ImportError("fixture optional dependency unavailable")

    monkeypatch.setattr(fit.importlib, "import_module", missing)
    with pytest.raises(fit.RigidCorrespondenceUnavailable):
        fit.fit_rigid_correspondence(dataset())


def test_unverified_observations_remain_unqualified_and_no_authority():
    result = fit.fit_rigid_correspondence(
        replace(
            dataset(), origin=fit.CorrespondenceOrigin.UNVERIFIED_SUPPLIED_OBSERVATIONS
        )
    )
    assert result.diagnostic_pass
    provenance = result.to_dict()["provenance"]
    assert provenance["origin"] == "UNVERIFIED_SUPPLIED_OBSERVATIONS"
    for key in (
        "physical_authority",
        "physical_calibration_qualified",
        "hardware_accessed",
        "registry_written",
        "held_out_used_for_fit",
        "scale_or_shear_fitted",
    ):
        assert provenance[key] is False
    assert provenance["physical_release_effect"] == "NONE"


def test_full_hard_point_budget_is_finite_and_round_trips():
    training = tuple(
        ((i % 7) * 10, ((i // 7) % 6) * 8, (i // 42) * 9 + (i % 3) * 2)
        for i in range(126)
    )
    data = dataset(training=training, held_out=((14, 19, -8), (-12, 13, 29)))
    result = fit.fit_rigid_correspondence(data)
    assert result.diagnostic_pass
    assert len(result.to_dict()["residuals"]) == fit.MAX_POINTS
    assert len(result.canonical_bytes()) < fit.MAX_EVIDENCE_BYTES
    assert verify(result, data).canonical_bytes() == result.canonical_bytes()


def test_constructor_import_and_verification_do_not_activate_optional_numpy(
    nominal, monkeypatch
):
    data, result = nominal

    def no_optional_import(*args, **kwargs):
        raise AssertionError(
            "inert constructors and verification must not import NumPy"
        )

    monkeypatch.setattr(fit.importlib, "import_module", no_optional_import)
    assert dataset().input_sha256 == data.input_sha256
    assert fit.RigidCorrespondencePolicy().policy_sha256 == (
        fit.DEFAULT_RIGID_CORRESPONDENCE_POLICY.policy_sha256
    )
    assert verify(result, data).diagnostic_pass


def test_overflow_policy_is_a_typed_bounded_refusal():
    with pytest.raises(fit.RigidCorrespondenceError) as error:
        replace(
            fit.DEFAULT_RIGID_CORRESPONDENCE_POLICY, maximum_training_rms_mm=10**1000
        )
    assert error.value.code == "INVALID_NUMBER"
