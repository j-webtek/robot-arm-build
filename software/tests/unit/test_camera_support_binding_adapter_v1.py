from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.camera_support_binding_adapter_v1 import (
    CameraSupportBindingAdapterError,
    CameraSupportOriginalReviewV1,
    load_camera_support_binding_v1,
    load_camera_support_bindings_v1,
)
from rocell.application.camera_support_optics_epoch_intake_v1 import (
    REQUIRED_BINDINGS,
    assess_camera_support_optics_epoch_intake_v1,
    build_camera_support_optics_epoch_intake_v1,
    camera_support_optics_epoch_component_v1,
)


ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = ROOT / "software/ai/schemas"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _prepare(root: Path, *, measured: int = 10, valid_until: int = 100):
    evidence = root / "originals"
    reviews = root / "reviews"
    evidence.mkdir(parents=True)
    reviews.mkdir()
    paths = []
    records = []
    for binding_id in REQUIRED_BINDINGS:
        payload = f"retained-original:{binding_id}".encode()
        relative = f"originals/{binding_id}.bin"
        (root / relative).write_bytes(payload)
        review = CameraSupportOriginalReviewV1(
            review_id=f"review-{binding_id}",
            binding_id=binding_id,
            evidence_relative_path=relative,
            evidence_sha256=hashlib.sha256(payload).hexdigest(),
            measured_monotonic_ns=measured,
            valid_until_monotonic_ns=valid_until,
            owner_ai_reviewer_id="owner-ai-camera-reviewer-v1",
            limitations=("Retained original authenticated; no hardware authority.",),
        )
        review_relative = f"reviews/{binding_id}.json"
        (root / review_relative).write_text(
            _canonical(review.to_dict()), encoding="utf-8")
        paths.append(review_relative)
        records.append(review)
    return tuple(paths), tuple(records)


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_four_retained_originals_bridge_to_arm070_and_grant_no_authority(
    tmp_path: Path,
):
    paths, reviews = _prepare(tmp_path)
    receipts = load_camera_support_bindings_v1(
        tmp_path, review_relative_paths=paths)
    assert tuple(item.binding.binding_id for item in receipts) == REQUIRED_BINDINGS
    assert tuple(item.review for item in receipts) == reviews
    for receipt in receipts:
        data = receipt.to_dict()
        jsonschema.Draft202012Validator(_schema(
            "camera_support_binding_adapter_receipt_v1.schema.json"
        )).validate(data)
        assert data["epoch_advanced"] is False
        assert data["camera_open_authorized"] is False
        assert data["controller_start_authorized"] is False
        assert data["transport_authorized"] is False
        assert data["execution_authorized"] is False
        assert data["hardware_access"] is False
        assert data["physical_authority"] is False

    intake = build_camera_support_optics_epoch_intake_v1(
        ROOT, bindings=tuple(item.binding for item in receipts))
    assessment = assess_camera_support_optics_epoch_intake_v1(
        intake, evaluated_monotonic_ns=20)
    component = camera_support_optics_epoch_component_v1(intake, assessment)
    assert assessment.ready is True
    assert component.component.value == "camera_support_optics"
    assert [item.binding_id for item in component.binding_evidence] == list(
        REQUIRED_BINDINGS)
    with pytest.raises(CameraSupportBindingAdapterError,
                       match="receipt and review evidence hashes differ"):
        replace(receipts[0], evidence_file_sha256="0" * 64)


def test_review_documents_match_closed_schema_and_round_trip(tmp_path: Path):
    paths, reviews = _prepare(tmp_path)
    schema = _schema("camera_support_original_owner_ai_review_v1.schema.json")
    for path, expected in zip(paths, reviews, strict=True):
        document = json.loads((tmp_path / path).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(document)
        receipt = load_camera_support_binding_v1(
            tmp_path, review_relative_path=path)
        assert receipt.review == expected


def test_tampered_original_and_review_hash_fail_closed(tmp_path: Path):
    paths, _ = _prepare(tmp_path)
    (tmp_path / "originals/camera_receipt.bin").write_bytes(b"substitution")
    with pytest.raises(CameraSupportBindingAdapterError,
                       match="differs from the accepted review"):
        load_camera_support_binding_v1(
            tmp_path, review_relative_path=paths[0])

    paths, _ = _prepare(tmp_path / "fresh")
    review_path = tmp_path / "fresh" / paths[0]
    document = json.loads(review_path.read_text(encoding="utf-8"))
    document["review_sha256"] = "0" * 64
    review_path.write_text(_canonical(document), encoding="utf-8")
    with pytest.raises(CameraSupportBindingAdapterError,
                       match="review hash differs"):
        load_camera_support_binding_v1(
            tmp_path / "fresh", review_relative_path=paths[0])


def test_duplicate_fields_wrong_order_partial_set_and_traversal_are_rejected(
    tmp_path: Path,
):
    paths, reviews = _prepare(tmp_path)
    duplicate = tmp_path / "reviews/duplicate.json"
    duplicate.write_text(
        '{"schema":"first","schema":"second"}', encoding="utf-8")
    with pytest.raises(CameraSupportBindingAdapterError,
                       match="duplicate owner-AI review field"):
        load_camera_support_binding_v1(
            tmp_path, review_relative_path="reviews/duplicate.json")

    with pytest.raises(CameraSupportBindingAdapterError,
                       match="canonical order"):
        load_camera_support_bindings_v1(
            tmp_path, review_relative_paths=paths[:-1])
    with pytest.raises(CameraSupportBindingAdapterError,
                       match="canonical order"):
        load_camera_support_bindings_v1(
            tmp_path, review_relative_paths=tuple(reversed(paths)))

    escaped = replace(reviews[0], evidence_relative_path="../outside.bin")
    escaped_path = tmp_path / "reviews/escaped.json"
    escaped_path.write_text(_canonical(escaped.to_dict()), encoding="utf-8")
    with pytest.raises(CameraSupportBindingAdapterError,
                       match="not a safe relative path"):
        load_camera_support_binding_v1(
            tmp_path, review_relative_path="reviews/escaped.json")


def test_authority_mutation_and_invalid_limitations_are_rejected(tmp_path: Path):
    paths, _ = _prepare(tmp_path)
    path = tmp_path / paths[0]
    document = json.loads(path.read_text(encoding="utf-8"))
    document["execution_authorized"] = True
    path.write_text(_canonical(document), encoding="utf-8")
    with pytest.raises(CameraSupportBindingAdapterError,
                       match="authority differs"):
        load_camera_support_binding_v1(
            tmp_path, review_relative_path=paths[0])

    paths, _ = _prepare(tmp_path / "wrong-type")
    path = tmp_path / "wrong-type" / paths[0]
    document = json.loads(path.read_text(encoding="utf-8"))
    document["limitations"] = "not-an-array"
    path.write_text(_canonical(document), encoding="utf-8")
    with pytest.raises(CameraSupportBindingAdapterError,
                       match="must be a JSON array"):
        load_camera_support_binding_v1(
            tmp_path / "wrong-type", review_relative_path=paths[0])


def test_adapter_authenticates_stale_evidence_but_arm070_blocks_it(tmp_path: Path):
    paths, _ = _prepare(tmp_path, measured=10, valid_until=15)
    receipts = load_camera_support_bindings_v1(
        tmp_path, review_relative_paths=paths)
    intake = build_camera_support_optics_epoch_intake_v1(
        ROOT, bindings=tuple(item.binding for item in receipts))
    assessment = assess_camera_support_optics_epoch_intake_v1(
        intake, evaluated_monotonic_ns=20)
    assert assessment.ready is False
    assert all(status == "BLOCKED"
               for _, status, _ in assessment.binding_statuses)
    assert all(blockers == ("EVIDENCE_STALE",)
               for _, _, blockers in assessment.binding_statuses)
