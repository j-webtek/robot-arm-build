"""Fast stage-5 reader join guards with an explicitly fake predecessor.

The fake prefix is NOT an authenticated original. These tests isolate routing,
closed package parsing and dependency comparison; full composition is covered
by test_camera_mode_entry_readback.py.
"""

from copy import deepcopy

import pytest

from rocell.application import physical_camera_mode_entry_readback as reader
from rocell.application import physical_camera_usb_complete_readback as complete
from rocell.application.physical_camera_mode_entry import HASH_FIELDS
from test_camera_mode_entry_layout import case, entry, binding, no_effects


def packages(case):
    return {
        case.ref.evidence_id: {
            "entry_id": case.entry.to_dict()["entry_id"],
            "record": deepcopy(case.record),
        }
    }


def invoke(case, records):
    # Exactly the full snapshot supplied at the owner boundary. The other
    # arguments are intentionally incapable modeled predecessor packages.
    return reader.verify_camera_mode_entry_workflow(
        {},
        case.snapshot,
        case.snapshot.header.header_sha256,
        *({} for _ in range(15)),
        records,
    )


def test_structural_package_is_not_original_authentication(case):
    result = reader.read_camera_mode_entry_layout(case.snapshot, packages(case))
    assert result.state == "ENTERED"
    assert result.original_store_authenticated is False


@pytest.mark.parametrize(
    "fault",
    [
        "extra_package",
        "extra_key",
        "wrong_id",
        "alias_key",
        "extra_record_key",
        "digest",
        "retention",
    ],
)
def test_bad_package_never_reaches_complete_predecessor(case, monkeypatch, fault):
    records = packages(case)
    record = records[case.ref.evidence_id]
    if fault == "extra_package":
        records["unexpected"] = deepcopy(record)
    elif fault == "extra_key":
        record["approved"] = True
    elif fault == "wrong_id":
        record["entry_id"] = "cameramode-" + "f" * 32
    elif fault == "alias_key":
        records["unexpected"] = records.pop(case.ref.evidence_id)
    elif fault == "extra_record_key":
        record["record"]["original_store_authenticated"] = True
    elif fault == "digest":
        record["record"]["evidence_sha256"] = "f" * 64
    else:
        record["record"]["retention"] = "M1_PUBLISHED_READBACK_PENDING"

    def denied(*args, **kwargs):
        pytest.fail("malformed suffix reached predecessor")

    monkeypatch.setattr(complete, "_verify_usb_complete_prefix", denied)
    with pytest.raises(reader.CameraModeOriginalError):
        invoke(case, records)


def test_valid_suffix_cannot_skip_complete_original_authentication(case, monkeypatch):
    before = deepcopy(case.snapshot)

    def reject(*args, **kwargs):
        assert args[1] is case.snapshot
        assert kwargs["camera_mode_entry"].reference == case.ref
        raise RuntimeError("MODELED_PREDECESSOR_REJECTED")

    monkeypatch.setattr(complete, "_verify_usb_complete_prefix", reject)
    with pytest.raises(RuntimeError, match="MODELED_PREDECESSOR_REJECTED"):
        invoke(case, packages(case))
    assert case.snapshot == before


@pytest.mark.parametrize("field", sorted(HASH_FIELDS))
def test_every_dependency_is_compared_after_predecessor_read(case, monkeypatch, field):
    # Model successful owner authentication ONLY at this seam, then change its
    # independently derived dependency. A well-formed self-bound suffix loses.
    authenticated = object()
    calls = []

    def predecessor(*args, **kwargs):
        assert args[1] is case.snapshot
        calls.append("original")
        return authenticated

    def derive(workflow, *, entry_launch_id):
        assert workflow is authenticated and calls == ["original"]
        assert entry_launch_id == case.binding["entry_launch_id"]
        expected = dict(case.binding)
        expected[field] = "f" * 64 if expected[field] != "f" * 64 else "e" * 64
        calls.append("derive")
        return expected

    monkeypatch.setattr(complete, "_verify_usb_complete_prefix", predecessor)
    monkeypatch.setattr(reader, "camera_mode_entry_binding", derive)
    with pytest.raises(ValueError):
        invoke(case, packages(case))
    assert calls == ["original", "derive"]
