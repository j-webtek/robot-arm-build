from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from rocell.vision.camera_profile import load_camera_profile
from rocell.vision.camera_receipt import (
    B0477_CAMERA_RECEIPT_SCHEMA,
    MAX_B0477_CAMERA_RECEIPT_BYTES,
    B0477CameraReceipt,
    CameraReceiptError,
    CameraReceiptIdentity,
    CameraReceiptLensIdentity,
    CameraReceiptMismatchError,
    compare_b0477_camera_receipt,
    make_synthetic_b0477_camera_receipt,
    parse_b0477_camera_receipt_json,
    require_matching_b0477_camera_receipt,
    synthetic_b0477_camera_receipt_document,
)


def _payload(document: object, *, sort_keys: bool = False) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=sort_keys,
        separators=(",", ":"),
    ).encode("utf-8")


def test_nominal_receipt_is_typed_digest_bound_and_has_zero_authority() -> None:
    receipt = make_synthetic_b0477_camera_receipt()
    assessment = compare_b0477_camera_receipt(receipt, load_camera_profile())

    assert receipt.fixture_class == "SYNTHETIC_ZERO_HARDWARE"
    assert receipt.identity == CameraReceiptIdentity(
        manufacturer="Arducam",
        model="B0477",
        sensor="Sony IMX283",
        lens=CameraReceiptLensIdentity(
            mount="C-mount",
            focal_length_mm=16.0,
            supply_relationship="included with B0477",
        ),
    )
    assert receipt.hardware_accessed is False
    assert receipt.physical_receipt_verified is False
    assert receipt.live_ready is False
    assert len(receipt.unmeasured_physical) == 15
    assert set(receipt.unmeasured_physical.values()) == {None}
    assert receipt.to_dict()["authority"] == {
        "hardware_accessed": False,
        "physical_receipt_verified": False,
        "camera_opened": False,
        "camera_frames_requested": 0,
        "arm_commands": 0,
        "hardware_presence_authority": False,
        "live_capture_authority": False,
        "calibration_authority": False,
        "robot_motion_authority": False,
        "contact_authority": False,
        "physical_release_effect": "NONE",
    }
    assert assessment.matched is True
    assert assessment.failed_check_ids == ()
    assert assessment.detail_code == "SYNTHETIC_B0477_RECEIPT_MATCH"
    assert assessment.receipt_canonical_sha256 == receipt.canonical_sha256
    assert assessment.hardware_accessed is False
    assert assessment.physical_receipt_verified is False
    assert assessment.physical_release_effect == "NONE"


@pytest.mark.parametrize(
    ("override", "failed_check"),
    [
        ({"manufacturer": "Other Camera Co"}, "manufacturer_matches"),
        ({"model": "B0478"}, "model_matches"),
        ({"sensor": "Sony IMX519"}, "sensor_matches"),
        ({"lens_mount": "CS-mount"}, "lens_mount_matches"),
        ({"lens_focal_length_mm": 12.0}, "lens_focal_length_matches"),
        (
            {"lens_supply_relationship": "separately purchased lens"},
            "lens_supply_relationship_matches",
        ),
    ],
)
def test_each_valid_wrong_identity_is_hashed_then_rejected(
    override: dict[str, object], failed_check: str
) -> None:
    profile = load_camera_profile()
    nominal = make_synthetic_b0477_camera_receipt()
    wrong = make_synthetic_b0477_camera_receipt(**override)  # type: ignore[arg-type]
    assessment = compare_b0477_camera_receipt(wrong, profile)

    assert wrong.canonical_sha256 != nominal.canonical_sha256
    assert assessment.receipt_canonical_sha256 == wrong.canonical_sha256
    assert assessment.matched is False
    assert assessment.detail_code == "SYNTHETIC_B0477_RECEIPT_MISMATCH_BLOCKED"
    assert assessment.failed_check_ids == (failed_check,)
    with pytest.raises(CameraReceiptMismatchError, match=failed_check):
        require_matching_b0477_camera_receipt(wrong, profile)


def test_canonical_digest_hashes_actual_normalized_object() -> None:
    wrong = make_synthetic_b0477_camera_receipt(model="NOT-B0477")
    canonical = json.dumps(
        wrong.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

    assert wrong.canonical_sha256 == hashlib.sha256(canonical).hexdigest()
    assert wrong.to_dict()["identity"] != (
        make_synthetic_b0477_camera_receipt().to_dict()["identity"]
    )


def test_canonical_digest_is_semantic_and_source_digest_is_byte_exact() -> None:
    document = synthetic_b0477_camera_receipt_document()
    compact = _payload(document, sort_keys=True)
    pretty = json.dumps(document, indent=5, ensure_ascii=False).encode("utf-8")

    compact_receipt = parse_b0477_camera_receipt_json(compact)
    pretty_receipt = parse_b0477_camera_receipt_json(pretty)

    assert compact_receipt.canonical_sha256 == pretty_receipt.canonical_sha256
    assert compact_receipt.source_file_sha256 != pretty_receipt.source_file_sha256
    assert compact_receipt.source_file_sha256 == hashlib.sha256(compact).hexdigest()


def test_source_path_is_resolved_without_opening_hardware(tmp_path: Path) -> None:
    relative = tmp_path / "fixtures" / "receipt.json"
    receipt = parse_b0477_camera_receipt_json(
        _payload(synthetic_b0477_camera_receipt_document()),
        source_path=relative,
    )

    assert receipt.source_path == relative.resolve()
    assert receipt.hardware_accessed is False


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda doc: doc.__setitem__("surprise", True), "unknown=.*surprise"),
        (lambda doc: doc.pop("identity"), "missing=.*identity"),
        (
            lambda doc: doc["identity"].__setitem__("marketing_name", "20MP"),
            "unknown=.*marketing_name",
        ),
        (
            lambda doc: doc["identity"]["lens"].pop("mount"),
            "missing=.*mount",
        ),
        (
            lambda doc: doc["unmeasured_physical"].__setitem__(
                "case_width_mm", 38.0
            ),
            "case_width_mm must remain null",
        ),
        (
            lambda doc: doc["authority"].__setitem__(
                "hardware_presence_authority", True
            ),
            "hardware_presence_authority",
        ),
        (
            lambda doc: doc["authority"].__setitem__("camera_frames_requested", 1),
            "camera_frames_requested",
        ),
        (
            lambda doc: doc.__setitem__("fixture_class", "PHYSICAL_RECEIPT"),
            "fixture_class",
        ),
    ],
)
def test_unknown_missing_measured_and_authority_mutations_fail_closed(
    mutation: Any, message: str
) -> None:
    document = deepcopy(synthetic_b0477_camera_receipt_document())
    mutation(document)

    with pytest.raises(CameraReceiptError, match=message):
        parse_b0477_camera_receipt_json(_payload(document))


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (True, "finite positive number"),
        (0, "within"),
        (-1.0, "within"),
        (1_001.0, "within"),
        ("16", "finite positive number"),
    ],
)
def test_malformed_lens_focal_length_fails_before_comparison(
    value: object, message: str
) -> None:
    document = synthetic_b0477_camera_receipt_document()
    document["identity"]["lens"]["focal_length_mm"] = value  # type: ignore[index]

    with pytest.raises(CameraReceiptError, match=message):
        parse_b0477_camera_receipt_json(_payload(document))


@pytest.mark.parametrize("value", ["", " B0477", "B0477 ", "B\x000477"])
def test_malformed_identity_text_fails(value: str) -> None:
    document = synthetic_b0477_camera_receipt_document(model=value)

    with pytest.raises(CameraReceiptError, match="identity.model"):
        parse_b0477_camera_receipt_json(_payload(document))


def test_strict_json_boundary_rejects_duplicates_nonfinite_and_bad_bytes() -> None:
    with pytest.raises(CameraReceiptError, match="duplicate key 'model'"):
        parse_b0477_camera_receipt_json(
            b'{"identity":{"model":"B0477","model":"B0478"}}'
        )
    with pytest.raises(CameraReceiptError, match="nonfinite JSON constant 'NaN'"):
        parse_b0477_camera_receipt_json(b'{"value":NaN}')
    with pytest.raises(CameraReceiptError, match="must be UTF-8"):
        parse_b0477_camera_receipt_json(b"\xff")
    with pytest.raises(CameraReceiptError, match="empty"):
        parse_b0477_camera_receipt_json(b"")
    with pytest.raises(CameraReceiptError, match="exceeds"):
        parse_b0477_camera_receipt_json(
            b" " * (MAX_B0477_CAMERA_RECEIPT_BYTES + 1)
        )
    with pytest.raises(CameraReceiptError, match="root must be an object"):
        parse_b0477_camera_receipt_json(b"[]")


def test_schema_version_and_evidence_semantics_are_exact() -> None:
    document = synthetic_b0477_camera_receipt_document()
    assert document["schema"] == B0477_CAMERA_RECEIPT_SCHEMA

    document["schema_version"] = True
    with pytest.raises(CameraReceiptError, match="schema_version"):
        parse_b0477_camera_receipt_json(_payload(document))

    document = synthetic_b0477_camera_receipt_document()
    document["evidence"]["claim_scope"] = "camera physically received"  # type: ignore[index]
    with pytest.raises(CameraReceiptError, match="evidence.claim_scope"):
        parse_b0477_camera_receipt_json(_payload(document))


def test_target_binding_mismatch_is_represented_and_rejected() -> None:
    document = synthetic_b0477_camera_receipt_document()
    document["target_profile"]["profile_id"] = "another-profile"  # type: ignore[index]
    receipt = parse_b0477_camera_receipt_json(_payload(document))
    assessment = compare_b0477_camera_receipt(receipt, load_camera_profile())

    assert assessment.matched is False
    assert assessment.failed_check_ids == ("target_profile_id_matches",)


def test_constructor_rejects_digest_that_does_not_bind_receipt_identity() -> None:
    nominal = make_synthetic_b0477_camera_receipt()

    with pytest.raises(CameraReceiptError, match="does not bind the actual"):
        B0477CameraReceipt(
            source_path=None,
            source_file_sha256=nominal.source_file_sha256,
            canonical_sha256=nominal.canonical_sha256,
            receipt_id=nominal.receipt_id,
            target_profile_schema=nominal.target_profile_schema,
            target_profile_id=nominal.target_profile_id,
            identity=CameraReceiptIdentity(
                manufacturer="Arducam",
                model="NOT-B0477",
                sensor="Sony IMX283",
                lens=nominal.identity.lens,
            ),
            unmeasured_physical=nominal.unmeasured_physical,
        )


def test_public_comparator_rejects_wrong_runtime_types() -> None:
    profile = load_camera_profile()
    receipt = make_synthetic_b0477_camera_receipt()

    with pytest.raises(TypeError, match="receipt"):
        compare_b0477_camera_receipt(object(), profile)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="profile"):
        compare_b0477_camera_receipt(receipt, object())  # type: ignore[arg-type]
