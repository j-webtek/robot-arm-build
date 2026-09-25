"""Stage-5 entry document contract; hashes here are explicitly MODELED data.

These tests cover pure encoding and exact context comparison, not an original
store, journal transition, camera admission, device call or received hardware.
The successor original reader/service must independently establish those facts.
"""

from copy import deepcopy
from dataclasses import FrozenInstanceError
import json

import pytest


# Import inside the fixture: the file can be prepared while a separately
# collected long acceptance run keeps the production source version fixed.
@pytest.fixture
def entry():
    from rocell.application import physical_camera_mode_entry

    return physical_camera_mode_entry


HASH_FIELDS = (
    "source_sha256",
    "header_sha256",
    "prerequisites_sha256",
    "stage_catalog_sha256",
    "stage_order_sha256",
    "stage_policy_sha256",
    "configuration_epochs_sha256",
    "selected_identity_sha256",
    "complete_series_sha256",
    "complete_assessment_sha256",
    "complete_review_sha256",
    "complete_review_event_sha256",
)
FALSE_FIELDS = (
    "physical_authority",
    "hardware_qualified",
    "native_release_allowed",
    "camera_capture_authorized",
    "arm_access_authorized",
    "device_io_performed",
    "authenticated_operator_identity",
)
ENTRY_ID = "cameramode-" + "9" * 32


@pytest.fixture
def binding():
    return dict(
        **{key: "a" * 64 for key in HASH_FIELDS},
        cell_id="wizard-physical-camera-" + "1" * 16,
        session_id="physical-camera-" + "2" * 32,
        origin_launch_id="wizard-" + "3" * 32,
        entry_launch_id="wizard-" + "4" * 32,
    )


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def make(entry, binding):
    return entry.build_camera_mode_entry(
        entry_id=ENTRY_ID,
        binding=binding,
        operator_id="MODELED setup operator",
        recorded_at_utc_ns=123456789,
    )


def test_entry_is_detached_canonical_data_without_stage_or_device_authority(
    entry, binding
):
    subject = make(entry, binding)
    document = subject.to_dict()
    assert document["schema"] == "rocell.camera_mode_entry.v1"
    assert document["stage"] == "camera_mode_controls"
    assert document["effect_class"] == "NO_DEVICE_IO"
    assert document["binding"] == binding
    assert document["entry_id"] == ENTRY_ID
    assert document["recorded_at_utc_ns"] == 123456789
    assert all(document[key] is False for key in FALSE_FIELDS)
    assert "stage_pass" not in document and "permit" not in document
    assert len(subject.payload) <= entry.MAX_ENTRY_BYTES == 16 * 1024
    assert canonical(document) == subject.payload
    assert entry.CameraModeEntry(subject.payload).payload == subject.payload
    assert (
        entry.verify_camera_mode_entry(
            subject.payload, expected_entry_id=ENTRY_ID, expected_binding=binding
        ).payload
        == subject.payload
    )
    binding["source_sha256"] = "b" * 64
    document["binding"]["source_sha256"] = "c" * 64
    assert subject.to_dict()["binding"]["source_sha256"] == "a" * 64
    with pytest.raises((AttributeError, FrozenInstanceError)):
        subject.payload = b"{}"


@pytest.mark.parametrize("field", HASH_FIELDS)
def test_every_original_dependency_is_compared_exactly(entry, binding, field):
    subject = make(entry, binding)
    changed = deepcopy(binding)
    changed[field] = "b" * 64
    with pytest.raises(entry.CameraModeEntryError):
        entry.verify_camera_mode_entry(
            subject.payload, expected_entry_id=ENTRY_ID, expected_binding=changed
        )


@pytest.mark.parametrize(
    "field",
    (
        "cell_id",
        "session_id",
        "origin_launch_id",
        "entry_launch_id",
    ),
)
def test_store_and_launch_context_are_not_interchangeable(entry, binding, field):
    subject = make(entry, binding)
    changed = deepcopy(binding)
    changed[field] = changed[field][:-1] + "8"
    with pytest.raises(entry.CameraModeEntryError):
        entry.verify_camera_mode_entry(
            subject.payload, expected_entry_id=ENTRY_ID, expected_binding=changed
        )


def test_entry_id_must_match_original_role_and_event_subject(entry, binding):
    subject = make(entry, binding)
    with pytest.raises(entry.CameraModeEntryError):
        entry.verify_camera_mode_entry(
            subject.payload,
            expected_entry_id="cameramode-" + "8" * 32,
            expected_binding=binding,
        )
    assert entry.camera_mode_entry_label(ENTRY_ID) == (
        "camera-mode-entry-v1:" + ENTRY_ID
    )
    assert entry.camera_mode_entry_event(ENTRY_ID) == ("CAMERA_MODE_ENTRY_" + "9" * 32)


@pytest.mark.parametrize("field", FALSE_FIELDS)
@pytest.mark.parametrize("value", (True, 0, 1, None, "false"))
def test_entry_cannot_encode_authority_or_loose_booleans(entry, binding, field, value):
    document = make(entry, binding).to_dict()
    document[field] = value
    with pytest.raises(entry.CameraModeEntryError):
        entry.CameraModeEntry(canonical(document))


@pytest.mark.parametrize(
    "field,value",
    (
        ("schema", "rocell.camera_mode_entry.v2"),
        ("stage", "camera_frame_freshness"),
        ("effect_class", "BOUNDED_CAMERA_CAMPAIGN"),
        ("entry_id", "cameramode-" + "A" * 32),
        ("entry_id", "cameramode-" + "0" * 31),
        ("entry_id", 1),
        ("recorded_at_utc_ns", True),
        ("recorded_at_utc_ns", 1.5),
        ("recorded_at_utc_ns", 0),
        ("recorded_at_utc_ns", -1),
        ("recorded_at_utc_ns", 2**63),
        ("operator_id", ""),
        ("operator_id", " leading"),
        ("operator_id", "trailing "),
        ("operator_id", "line\nbreak"),
        ("operator_id", "a" * 65),
        ("operator_id", "\u00e9" * 33),
        ("meaning", "Hardware ready"),
    ),
)
def test_closed_entry_contract(entry, binding, field, value):
    document = make(entry, binding).to_dict()
    document[field] = value
    with pytest.raises(entry.CameraModeEntryError):
        entry.CameraModeEntry(canonical(document))


@pytest.mark.parametrize("field", HASH_FIELDS)
@pytest.mark.parametrize("value", ("0" * 64, "A" * 64, "a" * 63, None, True))
def test_dependency_hashes_are_bounded_exact_nonzero_values(
    entry, binding, field, value
):
    binding[field] = value
    with pytest.raises(entry.CameraModeEntryError):
        make(entry, binding)


@pytest.mark.parametrize("place", ("document", "binding"))
@pytest.mark.parametrize("change", ("missing", "extra"))
def test_document_and_binding_fields_are_closed(entry, binding, place, change):
    document = make(entry, binding).to_dict()
    target = document if place == "document" else document["binding"]
    if change == "extra":
        target["unreviewed_override"] = True
    else:
        target.pop(next(iter(target)))
    with pytest.raises(entry.CameraModeEntryError):
        entry.CameraModeEntry(canonical(document))


@pytest.mark.parametrize(
    "kind",
    (
        "duplicate",
        "noncanonical",
        "oversize",
        "utf8",
        "array",
        "nan",
        "empty",
    ),
)
def test_parser_rejects_ambiguous_or_unbounded_bytes(entry, binding, kind):
    subject = make(entry, binding)
    raw = {
        "duplicate": b'{"schema":"duplicate",' + subject.payload[1:],
        "noncanonical": b" " + subject.payload,
        "oversize": b" " * (entry.MAX_ENTRY_BYTES + 1),
        "utf8": b"\xff",
        "array": b"[]",
        "nan": b'{"schema":NaN}',
        "empty": b"",
    }[kind]
    with pytest.raises(entry.CameraModeEntryError):
        entry.CameraModeEntry(raw)


@pytest.mark.parametrize("entry_id", (None, True, "", "../path", ENTRY_ID + "x"))
def test_role_and_event_names_never_accept_paths_or_partial_ids(entry, entry_id):
    for encode in (entry.camera_mode_entry_label, entry.camera_mode_entry_event):
        with pytest.raises(entry.CameraModeEntryError):
            encode(entry_id)
