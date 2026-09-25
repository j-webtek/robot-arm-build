from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import pytest

from rocell.vision.camera_commissioning import (
    CAMERA_COMMISSIONING_ASSESSMENT_SCHEMA,
    CAMERA_COMMISSIONING_REHEARSAL_SCHEMA,
    MAX_CAMERA_COMMISSIONING_REHEARSAL_BYTES,
    CameraCommissioningRehearsalError,
    assess_camera_commissioning_rehearsal,
    load_camera_commissioning_rehearsal,
    parse_camera_commissioning_rehearsal_json,
)
from rocell.vision.camera_profile import load_camera_profile


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "camera"
FIXTURE_PATH = FIXTURE_ROOT / "b0477_nominal_rehearsal.json"


def _document() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _payload(document: object) -> bytes:
    return json.dumps(document, ensure_ascii=False).encode("utf-8")


def test_nominal_fixture_passes_only_as_a_zero_hardware_rehearsal() -> None:
    rehearsal = load_camera_commissioning_rehearsal(
        FIXTURE_PATH.name,
        fixture_root=FIXTURE_ROOT,
    )
    assessment = assess_camera_commissioning_rehearsal(
        rehearsal,
        purchased_profile=load_camera_profile(),
    )

    assert rehearsal.source_path == FIXTURE_PATH.resolve()
    assert rehearsal.fixture_class == "SYNTHETIC_ZERO_HARDWARE"
    assert rehearsal.evidence_origin == "SYNTHETIC_TEST_FIXTURE"
    assert rehearsal.evidence_authority == "NO_PHYSICAL_EVIDENCE_AUTHORITY"
    assert len(rehearsal.devices) == 1
    assert rehearsal.camera.persistent_device_id.startswith("synthetic://")
    assert [item.reopen_index for item in rehearsal.camera.reopen_snapshots] == [1, 2]
    assert rehearsal.camera.reopen_snapshots[0].settings_sha256 == (
        rehearsal.camera.reopen_snapshots[1].settings_sha256
    )

    assert assessment.passed is True
    assert assessment.status == "SYNTHETIC_CAMERA_COMMISSIONING_REHEARSAL_PASS"
    assert assessment.commissioned is False
    assert assessment.hardware_accessed is False
    assert assessment.camera_frames_requested == 0
    assert assessment.arm_commands == 0
    assert assessment.physical_release_effect == "NONE"
    assert assessment.to_dict()["schema"] == CAMERA_COMMISSIONING_ASSESSMENT_SCHEMA
    assert len(assessment.canonical_sha256) == 64


def test_native_mode_manual_controls_and_observed_gain_are_exact() -> None:
    rehearsal = parse_camera_commissioning_rehearsal_json(FIXTURE_PATH.read_bytes())

    for snapshot in rehearsal.camera.reopen_snapshots:
        assert snapshot.negotiated_bus == "USB_3_2_GEN_1"
        assert (
            snapshot.mode.width_px,
            snapshot.mode.height_px,
            snapshot.mode.fps,
            snapshot.mode.fourcc,
        ) == (5472, 3648, 9.0, "YUY2")
        assert snapshot.controls.exposure_mode == "MANUAL"
        assert snapshot.controls.white_balance_mode == "MANUAL"
        assert snapshot.controls.gain_evidence == "SYNTHETIC_OBSERVATION"
        assert snapshot.controls.gain_observed == 1.0


def test_types_are_frozen_and_assessment_authority_cannot_be_replaced() -> None:
    rehearsal = parse_camera_commissioning_rehearsal_json(FIXTURE_PATH.read_bytes())
    assessment = assess_camera_commissioning_rehearsal(rehearsal)

    with pytest.raises(FrozenInstanceError):
        rehearsal.camera.device_id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        assessment.commissioned = True  # type: ignore[misc]


def test_canonical_digest_is_semantic_and_source_digest_is_byte_exact() -> None:
    document = _document()
    compact = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    pretty = json.dumps(document, indent=7, ensure_ascii=False).encode("utf-8")

    compact_record = parse_camera_commissioning_rehearsal_json(compact)
    pretty_record = parse_camera_commissioning_rehearsal_json(pretty)

    assert compact_record.canonical_sha256 == pretty_record.canonical_sha256
    assert compact_record.source_file_sha256 != pretty_record.source_file_sha256
    assert compact_record.source_file_sha256 == hashlib.sha256(compact).hexdigest()
    assert len(compact_record.canonical_sha256) == 64


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda doc: doc["devices"].append(deepcopy(doc["devices"][0])),
            "duplicate cameras",
        ),
        (
            lambda doc: doc["devices"][0].pop("persistent_device_id"),
            "missing=.*persistent_device_id",
        ),
        (
            lambda doc: doc["devices"][0].__setitem__(
                "persistent_device_id", "usb-real-device-id"
            ),
            "synthetic://",
        ),
        (
            lambda doc: doc["devices"][0]["reopen_snapshots"][0].__setitem__(
                "negotiated_bus", "USB_2_0"
            ),
            "negotiated_bus",
        ),
        (
            lambda doc: doc["devices"][0]["reopen_snapshots"][0]["mode"].__setitem__(
                "width_px", 3840
            ),
            "width_px",
        ),
        (
            lambda doc: doc["devices"][0]["reopen_snapshots"][0]["mode"].pop(
                "height_px"
            ),
            "missing=.*height_px",
        ),
        (
            lambda doc: doc["devices"][0]["reopen_snapshots"][0]["mode"].__setitem__(
                "fourcc", "MJPG"
            ),
            "fourcc",
        ),
        (
            lambda doc: doc["devices"][0]["reopen_snapshots"][0]["mode"].__setitem__(
                "fps", 8.0
            ),
            "fps",
        ),
        (
            lambda doc: doc["devices"][0]["reopen_snapshots"][0][
                "controls"
            ].__setitem__("exposure_mode", "AUTO"),
            "exposure_mode",
        ),
        (
            lambda doc: doc["devices"][0]["reopen_snapshots"][0][
                "controls"
            ].__setitem__("white_balance_mode", "AUTO"),
            "white_balance_mode",
        ),
        (
            lambda doc: doc["devices"][0]["reopen_snapshots"][1].__setitem__(
                "persistent_device_id",
                "synthetic://camera/arducam-b0477/different-unit",
            ),
            "identity drifted",
        ),
        (
            lambda doc: doc["devices"][0]["reopen_snapshots"][1][
                "controls"
            ].__setitem__("gain_observed", 2.0),
            "settings drifted",
        ),
        (
            lambda doc: doc["evidence"].__setitem__("origin", "PHYSICAL_CAPTURE"),
            "evidence.origin",
        ),
        (
            lambda doc: doc["evidence"].__setitem__(
                "authority", "PHYSICAL_COMMISSIONING_EVIDENCE"
            ),
            "evidence.authority",
        ),
        (
            lambda doc: doc["authority"].__setitem__("commissioned", True),
            "authority.commissioned",
        ),
        (
            lambda doc: doc["authority"].__setitem__("hardware_accessed", True),
            "authority.hardware_accessed",
        ),
        (
            lambda doc: doc["authority"].__setitem__("camera_frames_requested", 1),
            "authority.camera_frames_requested",
        ),
        (
            lambda doc: doc["authority"].__setitem__("arm_commands", 1),
            "authority.arm_commands",
        ),
        (
            lambda doc: doc["authority"].__setitem__(
                "physical_release_effect", "PASS"
            ),
            "authority.physical_release_effect",
        ),
        (lambda doc: doc.__setitem__("unknown", True), "unknown=.*unknown"),
        (lambda doc: doc["evidence"].pop("claim_scope"), "missing=.*claim_scope"),
    ],
)
def test_fixture_mutations_fail_closed(
    mutation: Callable[[dict[str, Any]], object], message: str
) -> None:
    document = deepcopy(_document())
    mutation(document)

    with pytest.raises(CameraCommissioningRehearsalError, match=message):
        parse_camera_commissioning_rehearsal_json(_payload(document))


def test_json_boundary_rejects_duplicate_nonfinite_invalid_and_oversize() -> None:
    with pytest.raises(CameraCommissioningRehearsalError, match="duplicate key"):
        parse_camera_commissioning_rehearsal_json(
            b'{"schema":"first","schema":"second"}'
        )
    nonfinite = FIXTURE_PATH.read_text(encoding="utf-8").replace(
        '"gain_observed": 1.0', '"gain_observed": NaN', 1
    )
    with pytest.raises(CameraCommissioningRehearsalError, match="nonfinite"):
        parse_camera_commissioning_rehearsal_json(nonfinite.encode("utf-8"))
    overflow = _document()
    overflow["devices"][0]["reopen_snapshots"][0]["controls"][
        "gain_observed"
    ] = 1e999
    with pytest.raises(CameraCommissioningRehearsalError, match="finite"):
        parse_camera_commissioning_rehearsal_json(_payload(overflow))
    with pytest.raises(CameraCommissioningRehearsalError, match="must be UTF-8"):
        parse_camera_commissioning_rehearsal_json(b"\xff")
    with pytest.raises(CameraCommissioningRehearsalError, match="empty"):
        parse_camera_commissioning_rehearsal_json(b"")
    with pytest.raises(CameraCommissioningRehearsalError, match="exceeds"):
        parse_camera_commissioning_rehearsal_json(
            b" " * (MAX_CAMERA_COMMISSIONING_REHEARSAL_BYTES + 1)
        )


def test_loader_rejects_path_escape_before_reading(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_bytes(FIXTURE_PATH.read_bytes())

    with pytest.raises(CameraCommissioningRehearsalError, match="escapes"):
        load_camera_commissioning_rehearsal(outside, fixture_root=root)


def test_schema_is_exact() -> None:
    document = _document()
    assert document["schema"] == CAMERA_COMMISSIONING_REHEARSAL_SCHEMA
    document["schema"] = "rocell.synthetic_camera_rehearsal.v0"
    with pytest.raises(CameraCommissioningRehearsalError, match="schema"):
        parse_camera_commissioning_rehearsal_json(_payload(document))
