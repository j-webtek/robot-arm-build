"""Pure camera part/index tests; process/camera observations are modeled."""

from copy import deepcopy
import re

import pytest

from rocell.application.camera_activation_campaign_evidence import (
    camera_activation_evidence,
)
from rocell.application.camera_activation_evidence_parts import (
    PART_BYTES,
    PART_KIND,
    INDEX_KIND,
    encode_camera_evidence_parts,
    inspect_camera_evidence_parts,
    part_name,
    index_name,
)
from rocell.application.commissioning_m1_persistence import _RECORD, MAX_RECORD_BYTES
from rocell.providers.windows import native_camera_activation_supervisor as supervisor
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
from rocell.providers.windows.native_camera_activation_registration import (
    prepare_owned_activation,
)
from rocell.providers.windows.native_camera_protocol import canonical
from test_native_camera_activation_registration import inputs, ready
from test_native_camera_activation_protocol import fixture as result_fixture
from test_native_camera_activation_evidence import modeled
from test_native_camera_activation_supervisor import (
    ModelOwner,
    Clock,
    no_physical_owner,
)

ATTEMPT = "attempt-" + "1" * 32
PERMIT = "f" * 64


def evidence(tmp_path, monkeypatch, purpose="probe", large=False):
    runtime, old_plan, expectation, args = inputs(tmp_path, purpose)
    request = old_plan.request
    client = WindowsCameraWorkerClient(
        runtime.to_dict()["helper"]["path"], request.helper_sha256
    )
    common = dict(
        source_sha256=request.source_sha256, campaign_id=ATTEMPT, budget=request.budget
    )
    plan = (
        client.prepare_probe(request.binding, **common)
        if purpose == "probe"
        else client.prepare_capture(
            request.binding,
            request.mode,
            tmp_path / ("capture-" + ATTEMPT),
            controls=request.controls,
            **common,
        )
    )
    args["session_id"] = "physical-camera-" + "2" * 32
    prepared = prepare_owned_activation(runtime, plan, expectation, **args)
    source_owner, owner_args = modeled(tmp_path, purpose)
    owner_args["ready_wire"] = ready(prepared)
    _, _, raw = result_fixture(purpose)
    raw["request_sha256"] = prepared.admission_request.request_sha256
    raw["permit_sha256"] = PERMIT
    source_owner.stdout = owner_args["ready_wire"] + canonical(raw) + b"\n"
    owner = ModelOwner(source_owner, owner_args)
    if large:
        owner.result = b"x" * (256 * 1024 - len(owner.ready))
    monkeypatch.setattr(supervisor, "_new_owner", lambda: owner)
    import threading

    outcome = supervisor._supervise(
        prepared,
        prepared.registration,
        revalidate_consumed_permit=lambda exact: None,
        cancellation=threading.Event(),
        deadline_ns=25_000_000_000,
        _clock=Clock(),
    )
    return camera_activation_evidence(prepared, outcome)


def envelopes(encoded):
    return {
        record.filename: {"kind": record.kind, "data": record.data()}
        for record in encoded
    }


def inspect(records, **kwargs):
    context = dict(expected_attempt_id=ATTEMPT, expected_permit_sha256=PERMIT)
    context.update(kwargs)
    return inspect_camera_evidence_parts(records, **context)


@pytest.mark.parametrize("purpose", ["probe", "capture"])
@pytest.mark.parametrize("large", [False, True])
def test_complete_pair_round_trip_with_existing_record_limits(
    tmp_path, monkeypatch, purpose, large
):
    original = evidence(tmp_path, monkeypatch, purpose, large)
    encoded = encode_camera_evidence_parts(original)
    assert encoded[-1].kind == INDEX_KIND and all(
        record.kind == PART_KIND for record in encoded[:-1]
    )
    assert all(_RECORD.fullmatch(record.filename) for record in encoded)
    assert all(
        len(canonical({"kind": record.kind, "data": record.data()})) < MAX_RECORD_BYTES
        for record in encoded
    )
    assert all(record.data()["payload_bytes"] <= PART_BYTES for record in encoded[:-1])
    result = inspect(envelopes(encoded))
    assert result.complete and result.artifacts == original
    assert result.part_count == len(encoded) - 1 <= 24
    if large:
        assert result.part_count > 4


def test_every_partial_publication_requires_final_index(tmp_path, monkeypatch):
    encoded = encode_camera_evidence_parts(evidence(tmp_path, monkeypatch, large=True))
    for published in range(len(encoded)):
        partial = inspect(envelopes(encoded[:published]))
        assert not partial.complete and partial.artifacts is None
        assert partial.part_count == published
    assert inspect(envelopes(encoded)).complete


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "extra",
        "role-order",
        "names-order",
        "hash",
        "length",
        "bool-length",
        "schema",
        "cross-permit",
        "cross-attempt",
    ],
)
def test_index_cannot_hide_missing_changed_or_substituted_parts(
    tmp_path, monkeypatch, fault
):
    records = envelopes(
        encode_camera_evidence_parts(evidence(tmp_path, monkeypatch, large=True))
    )
    final = records[index_name(ATTEMPT)]["data"]
    descriptor = final["evidence"][0]
    name = descriptor["parts"][0]
    if fault == "missing":
        del records[name]
    elif fault == "extra":
        records["receipt-" + ATTEMPT + "-camera_activation_extra_a.json"] = deepcopy(
            records[name]
        )
    elif fault == "role-order":
        final["evidence"].reverse()
    elif fault == "names-order":
        descriptor["parts"].reverse()
    elif fault == "hash":
        descriptor["payload_sha256"] = "9" * 64
    elif fault == "length":
        descriptor["payload_bytes"] -= 1
    elif fault == "bool-length":
        descriptor["payload_bytes"] = True
    elif fault == "schema":
        descriptor["schema"] = "rocell.some_other_schema.v1"
    elif fault == "cross-permit":
        final["permit_sha256"] = "9" * 64
    else:
        final["attempt_id"] = "attempt-" + "9" * 32
    with pytest.raises(ValueError):
        inspect(records)


@pytest.mark.parametrize(
    "field,value",
    [
        ("payload_base64", "%%%"),
        pytest.param("payload_base64", "x" * 100_000, id="oversized-base64"),
        ("payload_bytes", True),
        ("payload_sha256", "9" * 64),
        ("artifact_bytes", 0),
        ("artifact_bytes", 2 * 1024 * 1024),
        ("part_count", True),
        ("part_index", True),
        ("part_index", 16),
        ("role", "other"),
        ("attempt_id", "attempt-" + "9" * 32),
        ("permit_sha256", "9" * 64),
    ],
)
def test_malformed_partial_part_is_not_tolerated_as_incomplete(
    tmp_path, monkeypatch, field, value
):
    encoded = encode_camera_evidence_parts(evidence(tmp_path, monkeypatch))
    records = envelopes(encoded[:1])
    records[encoded[0].filename]["data"][field] = value
    with pytest.raises(ValueError):
        inspect(records)


def test_partial_artifact_metadata_must_be_consistent(tmp_path, monkeypatch):
    encoded = encode_camera_evidence_parts(evidence(tmp_path, monkeypatch, large=True))
    records = envelopes(encoded[:2])
    records[encoded[1].filename]["data"]["artifact_sha256"] = "9" * 64
    with pytest.raises(ValueError, match="GROUP_MISMATCH"):
        inspect(records)


@pytest.mark.parametrize(
    "attempt", ["attempt-1", "../other", "attempt-" + "a" * 33, None]
)
def test_record_names_require_formal_attempt_namespace(attempt):
    with pytest.raises(ValueError):
        index_name(attempt)
    with pytest.raises(ValueError):
        part_name(attempt, "run", 0)
