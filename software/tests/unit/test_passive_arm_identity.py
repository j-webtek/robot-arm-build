"""Fresh passive identity checks with host access forbidden, including physical shapes."""

from copy import deepcopy
import json

import pytest

from rocell.application.passive_arm_identity import (
    PassiveControllerSelection,
    MAX_RECHECK_AGE_NS,
)
from test_wizard_native_arm_metadata import (
    no_host_access,
    snapshot,
    generic_review,
    correlate,
    SESSION,
    SOURCE,
)


def prepared(mode="rehearsal"):
    review = generic_review(mode)
    original = correlate(review=review, mode=mode)
    selected = PassiveControllerSelection(json.dumps(original).encode())
    fresh = snapshot(mode=mode)
    start = original["snapshot"]["finished_monotonic_ns"] + 1
    fresh["started_monotonic_ns"] = start
    fresh["finished_monotonic_ns"] = start + 10
    values = dict(
        mode=mode,
        session_id=SESSION,
        source_sha256=SOURCE,
        operation_id="operation-new-passive-check",
        collection_not_before_ns=start,
        now_monotonic_ns=start + 11,
    )
    return selected, fresh, review, values


@pytest.mark.parametrize("mode", ["physical", "rehearsal"])
def test_matching_identity_is_not_a_stronger_arm_binding(mode):
    selected, fresh, review, values = prepared(mode)
    before = deepcopy((fresh, review, values))
    result = selected.recheck(fresh, review, **values)
    assert result["status"] == "METADATA_RECHECK_MATCHED"
    assert result["candidate_port"] == "COM91"
    assert result["firmware"] == "UNKNOWN"
    for key in (
        "atomic_handle_identity",
        "references_authenticated",
        "physical_authority",
        "connected",
        "physical_dispatch_available",
    ):
        assert result[key] is False
    assert (fresh, review, values) == before


@pytest.mark.parametrize(
    "field",
    [
        "persistent_port_path",
        "persistent_instance_id",
        "driver_provider",
        "driver_service",
        "driver_version",
        "driver_inf",
    ],
)
def test_changed_native_identity_or_driver_held(field):
    selected, fresh, review, values = prepared()
    fresh["native_observations"][0][field] += "-changed"
    result = selected.recheck(fresh, review, **values)
    assert "NATIVE_MAPPING_OR_DRIVER_CHANGED" in result["blockers"]
    assert result["candidate_port"] is None


@pytest.mark.parametrize(
    "kind", ["duplicate", "missing", "changed-port", "changed-unit", "incomplete"]
)
def test_fresh_mapping_faults_never_fall_back(kind):
    selected, fresh, review, values = prepared()
    if kind == "duplicate":
        fresh["native_observations"].append(deepcopy(fresh["native_observations"][0]))
    elif kind == "missing":
        fresh["native_observations"] = []
    elif kind == "changed-port":
        fresh["native_observations"][0]["port_name"] = "COM92"
    elif kind == "changed-unit":
        fresh["serial_inventory"]["candidates"][0]["usb_identity"][
            "unit_serial"
        ] = "OTHER-UNIT"
    else:
        fresh["collection_blockers"] = ["TEST_INCOMPLETE"]
    result = selected.recheck(fresh, review, **values)
    assert result["status"] == "HELD"
    assert result["candidate_port"] is None


def test_no_old_snapshot_replay_or_clock_renewal():
    selected, fresh, review, values = prepared()
    original = json.loads(selected.payload)
    result = selected.recheck(original["snapshot"], review, **values)
    assert "COLLECTION_NOT_AFTER_ORIGINAL" in result["blockers"]
    assert "FRESH_COLLECTION_REQUIRED" in result["blockers"]
    values["now_monotonic_ns"] = fresh["finished_monotonic_ns"] + MAX_RECHECK_AGE_NS + 1
    assert (
        "FRESH_COLLECTION_REQUIRED"
        in selected.recheck(fresh, review, **values)["blockers"]
    )


def test_new_operation_required():
    selected, fresh, review, values = prepared()
    values["operation_id"] = "operation-native"
    assert (
        "NEW_OPERATION_REQUIRED"
        in selected.recheck(fresh, review, **values)["blockers"]
    )


def test_caller_cannot_promote_held_report_by_editing_status():
    original = correlate(snapshot("missing-fields"))
    original["status"] = "METADATA_CORRELATED"
    original["blockers"] = []
    with pytest.raises(ValueError):
        PassiveControllerSelection(json.dumps(original).encode())


def test_boolean_clock_rejected():
    selected, fresh, review, values = prepared()
    values["now_monotonic_ns"] = True
    with pytest.raises(ValueError):
        selected.recheck(fresh, review, **values)


def test_physical_selection_cannot_be_rechecked_with_rehearsal_observations():
    physical, _, _, _ = prepared("physical")
    _, fresh, review, values = prepared("rehearsal")
    result = physical.recheck(fresh, review, **values)
    assert "ORIGINAL_MODE_MISMATCH" in result["blockers"]
    assert result["candidate_port"] is None


def test_repeated_new_review_is_not_the_retained_original():
    selected, fresh, _, values = prepared()
    result = selected.recheck(fresh, generic_review(), **values)
    assert "ORIGINAL_GENERIC_REVIEW_SHA256_MISMATCH" in result["blockers"]
    assert result["candidate_port"] is None


def test_source_change_rejected_before_returning_endpoint():
    selected, fresh, review, values = prepared()
    values["source_sha256"] = "b" * 64
    with pytest.raises(ValueError):
        selected.recheck(fresh, review, **values)
