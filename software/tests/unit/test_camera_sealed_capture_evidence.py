"""Pure future-store collection/part codec, modeled hashes, no original M1 seal."""

import base64
import copy

import pytest

from rocell.application import camera_sealed_capture_evidence as module
from rocell.application.camera_capture_checksum import (
    build_capture_checksum,
    capture_metadata,
    CameraCaptureChecksum,
)
from rocell.application.camera_activation_campaign_evidence import (
    validate_camera_activation_evidence,
)
from rocell.application.camera_activation_evidence_parts import (
    encode_camera_evidence_parts,
    inspect_camera_evidence_parts,
)
from rocell.providers.windows.camera_worker_client import NativeFrameArtifact
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_operating_evidence_preflight import case
from test_physical_camera_configuration import forbid_process_and_devices
from test_native_camera_activation_supervisor import no_physical_owner

ATTEMPT = "attempt-" + "7" * 32
KEY = "operation-" + "8" * 32


@pytest.fixture
def collection(tmp_path, monkeypatch):
    _, factory = case(tmp_path, monkeypatch, version="v2")
    native = factory(ATTEMPT).native
    checked, _, frame = capture_metadata(native.evidence)
    tick = checked.run.to_dict()["finished_ns"] + 1
    checksum = build_capture_checksum(
        native.evidence,
        request_key=KEY,
        status="CAPTURE_BYTES_HASHED",
        frame=NativeFrameArtifact(**frame, sha256="e" * 64),
        read_started_ns=tick,
        read_finished_ns=tick,
    )
    return module.SealedCameraCaptureEvidence(native.evidence, checksum)


def records(collection):
    return {
        part.filename: dict(kind=part.kind, data=part.data())
        for part in module.encode_sealed_capture_parts(collection)
    }


def inspect(collection, values=None, **kwargs):
    checked = validate_camera_activation_evidence(collection.native)
    args = dict(
        expected_attempt_id=ATTEMPT,
        expected_permit_sha256=checked.prepared.admission_request.to_dict()[
            "permit_sha256"
        ],
    )
    args.update(kwargs)
    return module.inspect_sealed_capture_parts(
        records(collection) if values is None else values, **args
    )


def test_roundtrip_uses_unchanged_native_parts_and_distinct_final_index(collection):
    encoded = module.encode_sealed_capture_parts(collection)
    native = encode_camera_evidence_parts(collection.native)
    assert encoded[:-2] == native[:-1]
    assert encoded[-1].kind == module.INDEX_KIND
    assert encoded[-1].kind != native[-1].kind
    actual = inspect(collection)
    assert actual.complete and actual.artifacts == collection
    assert actual.part_count == len(encoded) - 1
    assert collection.evidence_sha256s == (
        *[a.payload_sha256 for a in collection.native],
        collection.checksum.sha256,
    )
    assert collection.payload_bytes == sum(
        len(a.payload) for a in collection.native
    ) + len(collection.checksum.payload)
    assert all(
        not collection.checksum.to_dict()[key]
        for key in (
            "stage_passed",
            "original_store_authenticated",
            "hardware_qualified",
        )
    )


def test_every_interrupted_publication_prefix_is_incomplete_not_repaired(collection):
    encoded = module.encode_sealed_capture_parts(collection)
    for index in range(len(encoded)):
        values = {
            part.filename: dict(kind=part.kind, data=part.data())
            for part in encoded[:index]
        }
        before = copy.deepcopy(values)
        result = inspect(collection, values)
        assert not result.complete and result.artifacts is None
        assert result.part_count == index
        assert values == before


def test_legacy_pair_and_index_readers_reject_new_collection(collection):
    with pytest.raises(ValueError):
        validate_camera_activation_evidence(collection)
    checked = validate_camera_activation_evidence(collection.native)
    with pytest.raises(ValueError):
        inspect_camera_evidence_parts(
            records(collection),
            expected_attempt_id=ATTEMPT,
            expected_permit_sha256=checked.prepared.admission_request.to_dict()[
                "permit_sha256"
            ],
        )
    legacy = {
        part.filename: dict(kind=part.kind, data=part.data())
        for part in encode_camera_evidence_parts(collection.native)
    }
    with pytest.raises(ValueError):
        inspect(collection, legacy)


@pytest.mark.parametrize("role", ["checksum", "native"])
def test_final_index_cannot_hide_missing_original_parts(collection, role):
    values = records(collection)
    name = (
        module.checksum_part_name(ATTEMPT) if role == "checksum" else next(iter(values))
    )
    del values[name]
    with pytest.raises(ValueError):
        inspect(collection, values)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "wrong"),
        ("payload_bytes", True),
        ("payload_bytes", 0),
        ("payload_bytes", module.MAX_BYTES + 1),
        ("payload_base64", "!"),
        ("payload_base64", "A" * (module.MAX_BYTES * 2)),
        ("payload_sha256", "a" * 64),
        ("attempt_id", "attempt-" + "1" * 32),
        ("permit_sha256", "b" * 64),
    ],
    ids=[
        "schema",
        "bool-size",
        "zero-size",
        "oversize",
        "bad-base64",
        "oversize-base64",
        "hash",
        "attempt",
        "permit",
    ],
)
def test_malformed_checksum_part_is_rejected_even_without_index(
    collection, field, value
):
    values = records(collection)
    values[module.checksum_part_name(ATTEMPT)]["data"][field] = value
    for complete in (True, False):
        if not complete:
            del values[module.index_name(ATTEMPT)]
        with pytest.raises(ValueError):
            inspect(collection, values)


@pytest.mark.parametrize(
    "fault",
    [
        "kind",
        "extra",
        "descriptor",
        "native_index",
        "extra_part",
        "extra_checksum",
        "unknown_kind",
        "wrong_attempt",
        "wrong_permit",
    ],
)
def test_closed_roster_and_exact_context(collection, fault):
    values = records(collection)
    final = values[module.index_name(ATTEMPT)]
    kwargs = {}
    if fault == "kind":
        final["kind"] = "WRONG"
    elif fault == "extra":
        final["data"]["anything"] = True
    elif fault == "descriptor":
        final["data"]["checksum"]["payload_sha256"] = "a" * 64
    elif fault == "native_index":
        final["data"]["native_evidence"].reverse()
    elif fault == "extra_part":
        values["unregistered-name.json"] = copy.deepcopy(next(iter(values.values())))
    elif fault == "extra_checksum":
        values[module.checksum_part_name(ATTEMPT)]["data"]["approved"] = True
    elif fault == "unknown_kind":
        values[module.checksum_part_name(ATTEMPT)]["kind"] = "UNKNOWN"
    elif fault == "wrong_attempt":
        kwargs["expected_attempt_id"] = "attempt-" + "1" * 32
    else:
        kwargs["expected_permit_sha256"] = "a" * 64
    with pytest.raises(ValueError):
        inspect(collection, values, **kwargs)


def test_rehashing_changed_native_metadata_is_not_original_consistency(collection):
    values = records(collection)
    data = collection.checksum.to_dict()
    data["frame"]["media_timestamp_100ns"] += 1
    raw = canonical(data)
    checksum = values[module.checksum_part_name(ATTEMPT)]["data"]
    checksum.update(
        payload_base64=base64.b64encode(raw).decode("ascii"),
        payload_bytes=len(raw),
        payload_sha256=digest(raw),
    )
    values[module.index_name(ATTEMPT)]["data"]["checksum"].update(
        payload_bytes=len(raw), payload_sha256=digest(raw)
    )
    with pytest.raises(ValueError):
        inspect(collection, values)


def test_failed_pixel_read_collection_preserves_failure_without_inventing_a_hash(
    collection,
):
    data = collection.checksum.to_dict()
    checksum = build_capture_checksum(
        collection.native,
        request_key=KEY,
        status="PIXEL_READ_INTERRUPTED",
        frame=None,
        read_started_ns=data["read_started_ns"],
        read_finished_ns=data["deadline_ns"],
    )
    failed = module.SealedCameraCaptureEvidence(collection.native, checksum)
    assert inspect(failed).artifacts == failed
    assert failed.checksum.to_dict()["frame"] is None
    assert failed.checksum.to_dict()["verified_pixel_bytes"] == 0
